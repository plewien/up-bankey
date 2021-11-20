from category import Categories
from config import Config, TransactionType
from transaction import GenericTransaction, TransactionFactory

import math


def toSankeyMatic(source, target, amount):
	return "%s [%d] %s" % (source, int(amount), target)


class Stream:

	def __init__(self, source: str, target: str, transaction: GenericTransaction=None):
		self.source = source
		self.target = target
		self.transactions = [transaction] if transaction else []
		self.total = transaction.amount if transaction else 0

	def __str__(self):
		if self.total > 0:
			return toSankeyMatic(self.source, self.target, self.total)
		else:
			return toSankeyMatic(self.target, self.source, -self.total)

	def accumulate(self, transaction : GenericTransaction):
		self.transactions.append(transaction)
		self.total += transaction.amount

	def accumulateList(self, transactions : list):
		for transaction in transactions:
			self.accumulate(transaction)

	def accumulateByValue(self, value):
		self.total += value

	def roundTotal(self, awayFromZero=False):
		if self.total > 0 and awayFromZero or self.total < 0 and not awayFromZero:
			self.total = math.ceil(self.total)
		else:
			self.total = math.floor(self.total)

	def simplify(self):
		if self.total < 0:
			self.source, self.target = self.target, self.source
			self.total = -self.total
		pass

	def isBelowThreshold(self, threshold):
		return abs(self.total) < threshold


class Streams(dict):

	def __init__(self, config=None, name=None, translator=None, *arg, **kw):
		super(Streams, self).__init__(*arg, **kw)
		self.translator = translator
		self.config = config
		self.name = config.name if config else name
		pass

	def __str__(self):
		return "\n".join([str(stream) for stream in self.values_sorted_by_total()])

	@staticmethod
	def makeKey(source, target):
		return source + target

	def insert_impl(self, transaction, source, target):
		key = Streams.makeKey(source, target)
		if key in self:
			self[key].accumulate(transaction)
		else:
			source = self.translate(source)
			target = self.translate(target)
			self[key] = Stream(source, target, transaction)
		return self[key]

	def insert(self, transaction : GenericTransaction):
		self.insert_impl(transaction, self.config.getAlias(transaction), self.name)

	def insertByValue(self, value, source, target):
		key = Streams.makeKey(source, target)
		self[key] = Stream(source, target)
		self[key].accumulateByValue(value)

	def rename(self, stream : Stream, source=None, target=None):
		oldKey = Streams.makeKey(stream.source, stream.target)
		if oldKey not in self:
			return
		if source is None:
			source = stream.source
		if target is None:
			target = stream.target

		# Insert the new stream into the collection
		newKey = Streams.makeKey(source, target)
		if newKey in self:
			self[newKey].accumulateList(self[oldKey].transactions)
		else:
			self[newKey] = self[oldKey]
			self[newKey].source = source
			self[newKey].target = target
		del self[oldKey]
		pass

	def values_sorted_by_total(self):
		sort_key = lambda stream: abs(stream.total)
		return sorted(self.values(), key=sort_key, reverse=True)

	def total(self):
		return sum([stream.total for stream in self.values()])

	def translate(self, id):
		if (self.translator is not None) and (id in self.translator):
			return self.translator[id]
		return id

	def apply(self, apply):
		return [apply(k, s) for k, s in self.items()]

	def round(self):
		self.roundTo(self.total())

	def roundTo(self, total):
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
				self[k].roundTotal(awayFromZero=True)
				difference -= 1
			else:
				self[k].roundTotal(awayFromZero=False)


class ExpenseStreams(Streams):
	"""
	Streams for expenses are a special case, as we need to handle both parent and child categories.

	The streams in this class are for each parent category. The streams from the parent categories
	to the sub-categories are handled by the groups. All transactions from Up Bank are guaranteed
	to have both category types.
	"""
	def __init__(self, config, categories : Categories):
		super().__init__(config, categories.toTranslator())
		self.groups : dict(str, Streams) = dict()
		self.categories : Categories = categories

	def __str__(self):
		strings = [str(group) for group in self.groups.values()]
		strings += [super().__str__()]	# join the parent categories
		return "\n".join(strings)

	def insert(self, transaction : GenericTransaction):
		group = transaction.parentCategory
		self.insert_impl(transaction, group, self.name)
		if group not in self.groups:
			self.groups[group] = Streams(name=group, translator=self.categories.toSubcategoryTranslator(group))
		self.groups[group].insert_impl(transaction, transaction.category, group)

	def cleanup(self):
		for group in self.groups.values():
			for stream in group.copy().values():
				if stream.total > 0:
					print("Warning: Net positive expense found for category %s, review these transactions:" % stream.source)
					for t in stream.transactions:
						print("* %s: %s" % (t.settled_at.date(), t))
				self.consolidateSmallExpenses(stream)

	def consolidateSmallExpenses(self, stream):
		parent = stream.target
		relativeThreshold = self.config.relativeThreshold * self[Streams.makeKey(parent, self.name)].total
		threshold = max(self.config.absoluteThreshold, relativeThreshold)
		if stream.isBelowThreshold(threshold):
			self.groups[parent].rename(stream, source="Other "+parent)

	def round(self):
		super().round()
		for parent, group in zip(self.values(), self.groups.values()):
			group.roundTo(parent.total)


class TransactionCollection:

	def __init__(self, config : Config, categories : Categories):
		self.config = config
		self.factory = TransactionFactory()
		self.income = Streams(config.income)
		self.savings = Streams(config.savings)
		self.expenses = ExpenseStreams(config.expense, categories)
		pass

	def __str__(self):
		return "\n".join([str(collection) for collection in self.collections()])

	def collections(self):
		return [self.income, self.expenses, self.savings]

	def addTransactions(self, transactions):
		for t in self.factory.to_generic_transaction_list(transactions):
			type = self.config.classify(t)
			if type is TransactionType.Income:		self.income.insert(t)
			elif type is TransactionType.Expense:	self.expenses.insert(t)
			elif type is TransactionType.Savings:	self.savings.insert(t)
			else:
				if type is TransactionType.Ignore:
					message = "Ignoring transaction"
				else:
					message = "Unmatched transaction found"
				print("%s for %s" % (message, t))
		pass

	def cleanup(self):
		self.expenses.cleanup()
		pass

	def round(self):
		for collection in self.collections():
			collection.round()
		pass

	def link(self):
		difference = self.income.total() + self.expenses.total() + self.savings.total()
		self.savings.insertByValue(-difference, "Bank Account", self.savings.name)
		self.income.insertByValue(self.expenses.total(), self.expenses.name, self.income.name)
		self.income.insertByValue(self.savings.total(), self.savings.name, self.income.name)
		pass
