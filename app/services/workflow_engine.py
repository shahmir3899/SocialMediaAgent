"""Hybrid workflow engine for determining post routing."""

from app.core.logging import logger
from app.models.post import PostMode, PostType


# Rule map: post_type -> mode
WORKFLOW_RULES: dict[PostType, PostMode] = {
    PostType.EDUCATIONAL: PostMode.AUTO,
    PostType.ENGAGEMENT: PostMode.AUTO,
    PostType.PROMOTIONAL: PostMode.MANUAL,
    PostType.QUOTE: PostMode.AUTO,
    PostType.ANNOUNCEMENT: PostMode.MANUAL,
}


class WorkflowEngine:
    """Determines whether a post requires manual approval or can be auto-published."""

    def determine_mode(self, post_type: PostType) -> PostMode:
        """Apply workflow rules to determine the posting mode."""
        mode = WORKFLOW_RULES.get(post_type, PostMode.MANUAL)
        logger.debug(f"Workflow: {post_type.value} -> {mode.value}")
        return mode

    def requires_approval(self, post_type: PostType) -> bool:
        """Check if a post type requires human approval."""
        return self.determine_mode(post_type) == PostMode.MANUAL
