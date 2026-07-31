import uuid

from app.shared.events import DomainEvent


class FloorCreated(DomainEvent):
    floor_id: uuid.UUID


class UserFloorAccessGranted(DomainEvent):
    user_id: uuid.UUID
    floor_id: uuid.UUID


class UserFloorAccessRevoked(DomainEvent):
    user_id: uuid.UUID
    floor_id: uuid.UUID
