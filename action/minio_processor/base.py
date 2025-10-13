from abc import ABC, abstractmethod

class BaseProcessor(ABC):
    @abstractmethod
    async def process_notification(self, bucket_notification):
        raise NotImplementedError("process_notification method must be implemented by subclasses")