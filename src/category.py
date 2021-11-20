from upbankapi import Client
from upbankapi.models import ModelBase
from typing import Optional


class Category(ModelBase):

	def __init__(self, client: Client, data) -> None:
		super().__init__(client, data)
		self.id: str = data["id"]
		self.name: str = data["attributes"]["name"]

		relationships = data["relationships"]
		self.parent: Optional[str] = (
			relationships["parent"]["data"]["id"]
			if relationships["parent"]["data"]
			else None
		)
		self.children: Optional[list] = (
			[data["id"] for data in relationships["children"]["data"]]
			if relationships["children"]["data"]
			else None
		)
		pass

class Categories(ModelBase, dict):

	def __init__(self, client: Client, data) -> None:
		super().__init__(client, data)
		self.categories: dict = dict()
		for subdata in data["data"]:
			category = Category(client, subdata)
			self[category.id] = category
		pass

	def to_subtranslator(self, id):
		translator = {child : self[child].name for child in self[id].children}
		translator[id] = self[id].name  # include map for parent category
		return translator

	def to_translator(self):
		return {key : self[key].name for key in self.keys()}


if __name__ == "__main__":
	client = Client()
	data = client.api("/categories")
	categories = Categories(client, data)
	for k,v in categories.items():
		print(v.name)

