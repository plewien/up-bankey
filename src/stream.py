from transaction import GenericTransaction
import math


def toSankeyMatic(source, target, amount):
    return "%s [%d] %s" % (source, int(amount), target)


class Stream:

	def __init__(self, source: str, target: str, transaction: GenericTransaction=None):
		self.source = source
		self.target = target
		self.items = [transaction] if transaction else []
		self.total = transaction.amount if transaction else 0

	def __str__(self):
		if self.total > 0:
			return toSankeyMatic(self.source, self.target, self.total)
		else:
			return toSankeyMatic(self.target, self.source, -self.total)

	def accumulate(self, transaction : GenericTransaction):
		self.items.append(transaction)
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
	
	def isBelowThreshold(self, threshold):
		return abs(self.total) < threshold


class Streams(dict):
	
	def __init__(self, *arg, **kw):
		super(Streams, self).__init__(*arg, **kw)

	@staticmethod
	def makeKey(source, target):
		return source + target

	def insert(self, transaction, source, target):
		key = Streams.makeKey(source, target)
		if key in self:
			self[key].accumulate(transaction)
		else:
			self[key] = Stream(source, target, transaction)
		return self[key]

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
			self[newKey].accumulateList(self[oldKey].items)
		else:
			self[newKey] = self[oldKey]
			self[newKey].source = source
			self[newKey].target = target
		del self[oldKey]

	def total(self):
		return sum([stream.total for stream in self.values()])


class TransactionCollection:
	def __init__(self, config=None, name=None):
		self.name = config.name if config is not None else name
		self.config = config
		self.streams = Streams()

	def __str__(self):
		return "\n".join([str(stream) for stream in self.streams.values()])

	def insert(self, transaction : GenericTransaction):
		self.streams.insert(transaction, self.config.getAlias(transaction), self.name)

	def total(self):
		return self.streams.total()

	def applyToStreams(self, apply):
		return [apply(k, s) for k, s in self.streams.items()]

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
		totalWithTruncation = sum(self.applyToStreams(lambda _,s : math.trunc(s.total)))
		difference = math.floor(abs(total - totalWithTruncation))
		if difference > 0:
			zippedCentsAndKeys = self.applyToStreams(lambda k,s : (abs(s.total) % 1, k))
			zippedCentsAndKeys.sort(reverse=True)
			keysSortedByCents = [k for _,k in zippedCentsAndKeys]
		else:
			keysSortedByCents = self.streams.keys()
		
		for k in keysSortedByCents:
			if difference > 0:
				self.streams[k].roundTotal(awayFromZero=True)
				difference -= 1
			else:
				self.streams[k].roundTotal(awayFromZero=False)
		

class ExpensesCollection(TransactionCollection):

	def __init__(self, config):
		super().__init__(config)
		self.groups : dict(str, TransactionCollection) = dict()

	def __str__(self):
		strings = [str(group) for group in self.groups.values()]
		strings += [super().__str__()]  # join the parent categories
		return "\n".join(strings)

	def insert(self, transaction : GenericTransaction):
		group = transaction.parentCategory
		self.streams.insert(transaction, group, self.name)
		if group not in self.groups:
			self.groups[group] = TransactionCollection(name=group)
		self.groups[group].streams.insert(transaction, transaction.category, group)
	
	def cleanup(self):
		for group in self.groups.values():
			for stream in group.streams.copy().values():
				if stream.total > 0:
					print("Warning: Net positive expense found for category %s, review these transactions:" % stream.source)
					for t in stream.items:
						print("* %s: %s" % (t.settled_at.date(), t))
				self.consolidateSmallExpenses(stream)

	def consolidateSmallExpenses(self, stream):
		parent = stream.target
		relativeThreshold = self.config.relativeThreshold * self.streams[Streams.makeKey(parent, self.name)].total
		threshold = max(self.config.absoluteThreshold, relativeThreshold)
		if stream.isBelowThreshold(threshold):
			self.groups[parent].streams.rename(stream, source="Other "+parent)

	def round(self):
		super().round()
		for parent, group in zip(self.streams.values(), self.groups.values()):
			group.roundTo(parent.total)

	
class Linker(TransactionCollection):
	def __init__(self, income, expenses, savings):
		self.streams = Streams()
		difference = income.total() + expenses.total() + savings.total()
		savings.streams.insertByValue(-difference, "Bank Account", "Savings")
		self.streams.insertByValue(expenses.total(), expenses.name, income.name)
		self.streams.insertByValue(savings.total(), savings.name, income.name)
