from typing import Optional, List, Protocol, Union
from datetime import datetime

DEFAULT_PAGE_SIZE = 50

class Tag(Protocol):
	id : str
	"""Label and unique identifier"""


class Transaction(Protocol):
	@property
	def _raw_response(self) -> dict:
		...

	@property
	def created_at(self) -> datetime:
		...

	@property
	def description(self) -> str:
		...

	@property
	def amount(self) -> float:
		...

	@property
	def category(self):
		...

	@property
	def currency(self) -> str:
		...

	@property
	def tags(self) -> List[Tag]:
		...

	@property
	def message(self) -> Optional[str]:
		...


class Account(Protocol):
	@property
	def id(self):
		...

	@property
	def ownership_type(self):
		...


class Client(Protocol):
	def transactions(
		self,
		account: Union[str, Account] = None,
		*,
		since: datetime = None,
		until: datetime = None,
		category: str = None,
		limit: int = None,
		page_size: int = DEFAULT_PAGE_SIZE,
	): ...

	def accounts(
		self,
		*,
		limit: int = None,
	): ...

	def ping(self):
		...