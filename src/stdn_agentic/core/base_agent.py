"""
Abstract base class for all STDN agents
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseAgent(ABC, Generic[T]):
    """Abstract base class for all agents in STDN system"""

    def __init__(self, name: str, model: str):
        self.name = name
        self.model = model

    @abstractmethod
    async def run(self, prompt: str, **kwargs) -> T:
        """Run the agent with given prompt"""
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, model={self.model})"
