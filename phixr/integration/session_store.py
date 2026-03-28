"""Redis-backed session store for persistent session state.

Replaces in-memory dicts so sessions survive Phixr restarts and
can be shared across multiple instances.

Falls back to in-memory storage if Redis is unavailable.
"""

import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Session data TTL — 24 hours (sessions should be cleaned up long before this)
SESSION_TTL = 86400


class SessionStore:
    """Stores session mappings in Redis with in-memory fallback.

    Keys stored in Redis:
    - phixr:session:{session_id}        → JSON-serialized Session model
    - phixr:oc_id:{session_id}          → OpenCode session ID
    - phixr:oc_slug:{session_id}        → OpenCode session slug
    - phixr:issue:{project_id}:{issue_id} → Phixr session ID (active session for issue)
    """

    def __init__(self, redis_url: Optional[str] = None):
        self._redis = None
        self._memory: Dict[str, dict] = {}  # fallback
        self._oc_ids: Dict[str, str] = {}
        self._oc_slugs: Dict[str, str] = {}
        self._issue_map: Dict[str, str] = {}

        if redis_url:
            try:
                import redis
                self._redis = redis.Redis.from_url(redis_url, decode_responses=True)
                self._redis.ping()
                logger.info(f"Session store connected to Redis: {redis_url}")
            except Exception as e:
                logger.warning(f"Redis unavailable ({e}), using in-memory session store")
                self._redis = None
        else:
            logger.info("No Redis URL configured, using in-memory session store")

    @property
    def is_redis(self) -> bool:
        return self._redis is not None

    # ── Session CRUD ─────────────────────────────────────────────────────

    def save_session(self, session_id: str, session_data: dict) -> None:
        """Save a session (as dict from model_dump())."""
        if self._redis:
            self._redis.setex(
                f"phixr:session:{session_id}",
                SESSION_TTL,
                json.dumps(session_data, default=str),
            )
        else:
            self._memory[session_id] = session_data

    def get_session(self, session_id: str) -> Optional[dict]:
        if self._redis:
            data = self._redis.get(f"phixr:session:{session_id}")
            return json.loads(data) if data else None
        return self._memory.get(session_id)

    def delete_session(self, session_id: str) -> None:
        if self._redis:
            self._redis.delete(f"phixr:session:{session_id}")
        else:
            self._memory.pop(session_id, None)

    def list_sessions(self) -> List[dict]:
        if self._redis:
            keys = self._redis.keys("phixr:session:*")
            sessions = []
            for key in keys:
                data = self._redis.get(key)
                if data:
                    sessions.append(json.loads(data))
            return sessions
        return list(self._memory.values())

    def update_session_field(self, session_id: str, field: str, value) -> None:
        """Update a single field on a stored session."""
        data = self.get_session(session_id)
        if data:
            data[field] = value if not isinstance(value, datetime) else value.isoformat()
            self.save_session(session_id, data)

    # ── OpenCode ID / Slug Mapping ───────────────────────────────────────

    def set_opencode_id(self, session_id: str, oc_id: str) -> None:
        if self._redis:
            self._redis.setex(f"phixr:oc_id:{session_id}", SESSION_TTL, oc_id)
        else:
            self._oc_ids[session_id] = oc_id

    def get_opencode_id(self, session_id: str) -> Optional[str]:
        if self._redis:
            return self._redis.get(f"phixr:oc_id:{session_id}")
        return self._oc_ids.get(session_id)

    def set_opencode_slug(self, session_id: str, slug: str) -> None:
        if self._redis:
            self._redis.setex(f"phixr:oc_slug:{session_id}", SESSION_TTL, slug)
        else:
            self._oc_slugs[session_id] = slug

    def get_opencode_slug(self, session_id: str) -> Optional[str]:
        if self._redis:
            return self._redis.get(f"phixr:oc_slug:{session_id}")
        return self._oc_slugs.get(session_id)

    # ── Issue → Session Mapping ──────────────────────────────────────────

    def set_issue_session(self, project_id: int, issue_id: int, session_id: str) -> None:
        key = f"{project_id}:{issue_id}"
        if self._redis:
            self._redis.setex(f"phixr:issue:{key}", SESSION_TTL, session_id)
        else:
            self._issue_map[key] = session_id

    def get_issue_session(self, project_id: int, issue_id: int) -> Optional[str]:
        key = f"{project_id}:{issue_id}"
        if self._redis:
            return self._redis.get(f"phixr:issue:{key}")
        return self._issue_map.get(key)

    def clear_issue_session(self, project_id: int, issue_id: int) -> None:
        key = f"{project_id}:{issue_id}"
        if self._redis:
            self._redis.delete(f"phixr:issue:{key}")
        else:
            self._issue_map.pop(key, None)

    def clear_issue_session_by_session_id(self, session_id: str) -> None:
        """Remove issue mapping for a given session ID (scan needed)."""
        if self._redis:
            for key in self._redis.keys("phixr:issue:*"):
                if self._redis.get(key) == session_id:
                    self._redis.delete(key)
                    break
        else:
            for key, sid in list(self._issue_map.items()):
                if sid == session_id:
                    del self._issue_map[key]
                    break
