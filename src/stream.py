from .category import Categories
from .config import Config, TransactionType
from .transaction import GenericTransaction, TransactionFactory

import math


class Stream:

	def __init__(self, source: str, target: str, transaction: GenericTransaction=None):
		self.source = source
		self.target = target
		self.transactions = [transaction] if transaction else []
		self.total = transaction.amount if transaction else 0
		self.isOther = False

	def __str__(self):
		to_sankey_matic = lambda source, target, amt : "%s [%d] %s" % (source, int(amt), target)
		if self.total > 0:
			return to_sankey_matic(self.source, self.target, self.total)
		else:
			return to_sankey_matic(self.target, self.source, -self.total)

	def accumulate(self, transaction : GenericTransaction):
		self.transactions.append(transaction)
		self.total += transaction.amount

	def accumulate_list(self, transactions : list):
		for transaction in transactions:
			self.accumulate(transaction)

	def round_total(self, awayFromZero=False):
		if self.total > 0 and awayFromZero or self.total < 0 and not awayFromZero:
			self.total = math.ceil(self.total)
		else:
			self.total = math.floor(self.total)

	def simplify(self):
		if self.total < 0:
			self.source, self.target = self.target, self.source
			self.total = -self.total
		pass

	def is_below_threshold(self, threshold):
		return abs(self.total) < threshold


class Streams(dict):

	def __init__(self, config, *arg, **kw):
		super(Streams, self).__init__(*arg, **kw)
		self.config = config
		self.name = config.name
		pass

	def __str__(self):
		return "\n".join([str(stream) for stream in self.values_sorted()])

	def values_sorted(self):
		sort_key = lambda stream: (not stream.isOther, abs(stream.total))
		return sorted(self.values(), key=sort_key, reverse=True)

	def insert(self, transaction, source=None):
		if source is None:
			source = self._tosource(transaction)
		if source in self:
			self[source].accumulate(transaction)
		else:
			self[source] = Stream(source, self.name, transaction)
		pass

	def _tosource(self, transaction):
		return self.config.get_alias(transaction)

	def rename(self, stream : Stream, source):
		oldKey = stream.source
		if oldKey not in self:
			return

		# Insert the new stream into the collection
		if source in self:
			self[source].accumulate_list(self[oldKey].transactions)
		else:
			self[source] = self[oldKey]
			self[source].source = source
		del self[oldKey]
		pass

	def rename_as_other(self, stream : Stream):
		othername = "Other "+self.name
		self.rename(stream, source=othername)
		if othername in self:
			self[othername].isOther = True

	def consolidate_by_count(self, limit):
		difference = len(self) - limit
		if difference > 0:
			streamsNotOther = [x for x in self.values() if not x.isOther]
			streamsNotOther.sort(key = lambda stream: abs(stream.total))
			for stream in streamsNotOther[:difference]:
				self.rename_as_other(stream)

	def consolidate_by_total(self, relative, absolute):
		threshold = max(relative * self.total(), absolute)
		for stream in self.copy().values():
			if stream.isOther:
				continue
			if abs(stream.total) < abs(threshold):
				self.rename_as_other(stream)

	def total(self):
		return sum([stream.total for stream in self.values()])

	def apply(self, apply):
		return [apply(k, s) for k, s in self.items()]

	def validate(self):
		for stream in self.values():
			if self.config.outgoing and stream.total > 0:
				print("Warning: Outgoing stream found withe positive total, review these transactions:" % stream.source)
			elif not self.config.outgoing and stream.total < 0:
				print("Warning: Intended income stream found with negative total, review these transactions:" % stream.source)
			else:
				return
			for t in stream.transactions:
				print("* %s: %s" % (t.date.date(), t))

	def consolidate(self):
		self.consolidate_by_count(self.config.threshold.count)
		self.consolidate_by_total(relative=self.config.threshold.relative, absolute=self.config.threshold.absolute)
		pass

	def round(self):
		self.round_to(self.total())
		pass

	def round_to(self, total):
		"""
		Rounding requires some finesse to ensure the streams balance. Consider a simple example
		where there's three categories with totals $10.40, $10.30 and $10.30. Using rounding, these
		each would be valued at $10, for a total of $30. But the total for the parent category would
		be $31, off by a dollar. To round these properly, the first category should round to $11 and
		the others $10. Rounding up has been prioritised based on greatest amount of cents.
		"""
		totalWithTruncation = sum(self.apply(lambda _,s : math.trunc(s.total)))
		difference = math.floor(abs(total - totalWithTruncation))
		if difference > 0:
			zippedCentsAndKeys = self.apply(lambda k,s : (abs(s.total) % 1, k))
			zippedCentsAndKeys.sort(reverse=True)
			keysSortedByCents = [k for _,k in zippedCentsAndKeys]
		else:
			keysSortedByCents = self.keys()

		for k in keysSortedByCents:
			if difference > 0:
				self[k].round_total(awayFromZero=True)
				difference -= 1
			else:
				self[k].round_total(awayFromZero=False)


class ExpenseStreams(Streams):
	"""
	Streams for expenses are a special case, as we need to handle both parent and child categories.

	The streams in this class are for each parent category. The streams from the parent categories
	to the sub-categories are handled by the groups. All transactions from Up Bank are guaranteed
	to have both category types.
	"""
	def __init__(self, config):
		super().__init__(config)
		self.groups : dict(str, Streams) = dict()

	def __str__(self):
		strings = [str(group) for group in self.groups.values()]
		strings += [super().__str__()]	# join the parent categories
		return "\n".join(strings)

	def insert(self, transaction : GenericTransaction):
		super().insert(transaction)
		group = transaction.parentCategory
		if group not in self.groups:
			config = self.config
			config.name = group
			self.groups[group] = Streams(config)
		self.groups[group].insert(transaction, transaction.category)

	def _tosource(self, transaction):
		return transaction.parentCategory

	def validate(self):
		for group in self.groups.values():
			group.validate()

	def consolidate(self):
		for group in self.groups.values():
			group.consolidate()

	def round(self):
		super().round()
		for parent, group in zip(self.values(), self.groups.values()):
			group.round_to(parent.total)


class TransactionCollection:

	def __init__(self, config : Config, categories : Categories):
		self.config = config
		self.factory = TransactionFactory(categories)
		self.income = Streams(config.income)
		self.savings = Streams(config.savings)
		self.expenses = ExpenseStreams(config.expense)
		pass

	def __str__(self):
		return "\n".join([str(collection) for collection in self.collections()])

	def collections(self):
		return [self.income, self.expenses, self.savings]

	def add_transactions(self, transactions):
		generics = self.factory.to_generic_transactions(transactions)
		for t in self.config.filter(generics):
			type = self.config.classify(t)
			if type is TransactionType.Income:		self.income.insert(t)
			elif type is TransactionType.Expense:	self.expenses.insert(t)
			elif type is TransactionType.Savings:	self.savings.insert(t)
			else:
				print("Unmatched transaction found for", t)
		pass

	def cleanup(self):
		for collection in self.collections():
			collection.validate()
			collection.consolidate()
			collection.round()
		pass

	def link(self):
		difference = self.income.total() + self.expenses.total() + self.savings.total()
		self.savings.insert(self.factory.to_generic_transaction(-difference, "Bank Account"))
		self.income.insert(self.factory.to_generic_transaction(self.expenses.total(), self.expenses.name))
		self.income.insert(self.factory.to_generic_transaction(self.savings.total(), self.savings.name))
		pass
