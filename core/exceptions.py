"""
Custom exceptions for the Sovereign AI Agent Framework.

This module defines custom exceptions used throughout the framework
to provide more specific error handling and debugging capabilities.
"""

from uuid import UUID


class InvalidStateTransitionError(Exception):
    """Raised when an illegal state transition is attempted."""
    
    def __init__(self, from_state: str, to_state: str, task_id: UUID, message: str | None = None) -> None:
        """Initialize the invalid state transition error.
        
        Args:
            from_state: The current state before transition
            to_state: The attempted target state
            task_id: The task identifier
            message: Optional additional message
        """
        self.from_state = from_state
        self.to_state = to_state
        self.task_id = task_id
        self.message = message or f"Invalid state transition from {from_state} to {to_state}"
        super().__init__(self.message)


class WorkerNotFoundError(Exception):
    """Raised when a required worker cannot be found."""
    
    def __init__(self, worker_name: str, message: str | None = None) -> None:
        """Initialize the worker not found error.
        
        Args:
            worker_name: The name of the worker that was not found
            message: Optional additional message
        """
        self.worker_name = worker_name
        self.message = message or f"Worker '{worker_name}' not found"
        super().__init__(self.message)


class ApprovalDeniedError(Exception):
    """Raised when a required approval is denied."""
    
    def __init__(self, action: str, reason: str | None = None) -> None:
        """Initialize the approval denied error.
        
        Args:
            action: The action that was denied approval
            reason: Optional reason for denial
        """
        self.action = action
        self.reason = reason
        self.message = reason or f"Approval denied for action: {action}"
        super().__init__(self.message)

