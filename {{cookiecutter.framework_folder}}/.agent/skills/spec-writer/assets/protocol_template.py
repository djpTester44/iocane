"""
Protocol/ABC Template
=====================
Use this template when defining interfaces for new components.
"""

from abc import ABC, abstractmethod
from typing import Protocol, TypeVar

T = TypeVar("T")
InputT = TypeVar("InputT", contravariant=True)
OutputT = TypeVar("OutputT", covariant=True)


class ServiceProtocol(Protocol):
    """
    Protocol for [describe service responsibility].

    Responsibility: [Single Responsibility description]
    """

    def execute(self, input_data: dict) -> dict:
        """
        Execute the service operation.

        Args:
            input_data: [describe expected structure]

        Returns:
            [describe output structure]

        Raises:
            ValueError: If input validation fails
        """
        ...


class RepositoryABC[T](ABC):
    """
    Abstract Base Class for data repositories.

    Responsibility: Data access for [Entity] objects.
    """

    @abstractmethod
    def get(self, id: str) -> T | None:
        """Retrieve entity by ID."""
        ...

    @abstractmethod
    def save(self, entity: T) -> None:
        """Persist entity."""
        ...

    @abstractmethod
    def delete(self, id: str) -> bool:
        """Remove entity by ID. Returns True if deleted."""
        ...


class HandlerProtocol(Protocol[InputT, OutputT]):
    """
    Generic handler protocol for processing pipelines.

    Responsibility: Transform input to output.
    """

    def handle(self, input: InputT) -> OutputT:
        """Process input and return output."""
        ...
