from upbankapi.models import Transaction


def toSankeyMatic(source, target, amount):
    return "%s [%d] %s" % (source, amount, target)


class Stream:

	def __init__(self, source: str, target: str, transaction: Transaction=None):
		self.source = source
		self.target = target
		self.items = [transaction] if transaction else []
		self.total = transaction.amount if transaction else 0

	def __str__(self):
		if self.total > 0:
			return toSankeyMatic(self.source, self.target, self.total)
		else:
			return toSankeyMatic(self.target, self.source, -self.total)

	def accumulate(self, transaction : Transaction):
		self.items.append(transaction)
		self.total += transaction.amount

	def accumulateList(self, transactions : list):
		for transaction in transactions:
			self.accumulate(transaction)

	def accumulateByValue(self, value):
		self.total += value


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


class TransactionCollection:
	def __init__(self, config):
		self.name = config.name
		self.config = config
		self.streams = Streams()

	def __str__(self):
		return "\n".join([str(stream) for stream in self.streams.values()])

	def insert(self, transaction : Transaction):
		self.streams.insert(transaction, self.config.getAlias(transaction), self.name)

	def total(self):
		return sum([stream.total for stream in self.streams.values()])

	def totalIf(self, condition):
		return sum([stream.total for stream in self.streams.values() if condition(stream)])


class Expenses(TransactionCollection):

	def insert(self, transaction : Transaction):
		self.streams.insert(transaction, transaction.parentCategory, self.name)
		self.streams.insert(transaction, transaction.category, transaction.parentCategory)
	
	def cleanup(self):
		for stream in self.streams.copy().values():
			if stream.target != self.name:  # Only cleanup the child-categories
				if stream.total > 0:
					print("Warning: Net positive expense found for category %s, review these transactions:" % stream.source)
					for t in stream.items:
						print("* %s: %s" % (t.settled_at.date(), t))
				if abs(stream.total) < self.threshold(stream.target):
					self.streams.rename(stream, source="Other "+stream.target)

	def total(self):
		return self.totalIf(lambda stream: self.name in [stream.source, stream.target])

	def threshold(self, parent):
		return 0.05 * abs(self.streams[Streams.makeKey(parent, self.name)].total)


class Linker:
	def __init__(self, income, expenses, savings):
		self.streams = Streams()
		difference = income.total() + expenses.total() + savings.total()
		savings.streams.insertByValue(-difference, "Bank Account", "Savings")
		self.streams.insertByValue(expenses.total(), expenses.name, income.name)
		self.streams.insertByValue(savings.total(), savings.name, income.name)

	def __str__(self):
		return "\n".join([str(stream) for stream in self.streams.values()])

