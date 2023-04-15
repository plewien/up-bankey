from typing import Optional, List, Protocol, Union
from datetime import datetime

DEFAULT_PAGE_SIZE = 50

class Tag(Protocol):
	id : str
	"""Label and unique identifier"""


class CategoryBase(Protocol):
	id : Optional[str]
	name : str


class Category(CategoryBase):
	parent : Optional[CategoryBase]
	children : List[CategoryBase]


class Transaction(Protocol):
	_raw_response : dict
	created_at : datetime
	description : str
	amount : float
	category : Optional[Category]
	currency : str
	tags : List[Tag]
	message : Optional[str]


class Account(Protocol):
	id : Optional[str]

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
		category: Union[str, Category] = None,
		limit: int = None,
		page_size: int = DEFAULT_PAGE_SIZE,
	): ...

	def accounts(
		self,
		*,
		limit: int = None,
	): ...

	def categories(self) -> List[Category]:
		...

	def ping(self):
		...
