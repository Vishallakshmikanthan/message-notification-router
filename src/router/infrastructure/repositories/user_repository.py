"""UserRepository implementation matching users.csv dataset."""

from router.domain.entities.user import User
from router.domain.ports.repository_ports import IUserRepository
from router.infrastructure.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository[User, str], IUserRepository):
    """Stores recipient user profiles in memory."""

    pass
