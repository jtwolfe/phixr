"""Git utilities for Phixr.

Contains branch management, repository operations, and GitLab integration.
"""

from .branch_manager import BranchManager, get_branch_manager

__all__ = ['BranchManager', 'get_branch_manager']