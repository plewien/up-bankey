import yaml
import itertools
from enum import Enum
from transaction import GenericTransaction
from datetime import datetime
from dateutil import parser
from dateutil.relativedelta import relativedelta

def readYaml(filePath : str):
	with open(filePath, 'r') as f:
		return yaml.safe_load(f)

# Inspired by https://stackoverflow.com/questions/36831998/how-to-fill-default-parameters-in-yaml-file-using-python
def populateConfigRecursively(input: dict, default):
	for k in default:
		if isinstance(default[k], dict):  # populate the sub-config
			populateConfigRecursively(input.setdefault(k, {}), default[k])
		else:
			input.setdefault(k, default[k])

def isInternalTransaction(transaction: GenericTransaction):
	actions = ['Cover', 'Transfer', 'Forward', 'Quick save transfer']
	directions = ['from', 'to']
	internalDescriptions = ['%s %s ' % (a, d) for a, d in itertools.product(actions, directions)]
	internalDescriptions += ['Round Up', 'Bonus Payment']
	return transaction.description.startswith(tuple(internalDescriptions))

def toDateTime(input: str):
	if input is None:
		return None
	if input == "today" or input == "now":
		return datetime.now()
	if input.endswith("ago"):
		value, unit, _ = input.split()  # assumes format '1 year ago', etc
		return datetime.now() - relativedelta(**{unit: int(value)})
	return parser.parse(input)

class TransactionType(Enum):
	Unknown     = -2
	Ignore		= -1
	Income		= 0
	Expense     = 1
	Savings     = 2


class CollectionConfig:
	def __init__(self, config):
		self.name = config['name']
		self.tags = CollectionConfig.make_set(config['classifiers']['tags'])
		self.accounts = CollectionConfig.make_set(config['classifiers']['accounts'])
		self.tagAliases: dict = CollectionConfig.make_aliases(config['classifiers']['tags'])
		self.accountAliases: dict = CollectionConfig.make_aliases(config['classifiers']['accounts'])
		self.absoluteThreshold = config['threshold']['value']
		self.relativeThreshold = config['threshold']['percentage'] / 100

	@staticmethod
	def make_set(l : list):
		s = set()
		for elem in l:
			if isinstance(elem, dict):
				for k in elem.keys():
					s.add(k)
			else:
				s.add(elem)
		return s

	@staticmethod
	def make_aliases(l : list):
		listOfAliases = filter(lambda e: isinstance(e, dict), l)
		return {k:v for element in listOfAliases for (k,v) in element.items()}

	def get_alias(self, transaction : GenericTransaction):
		for tag in transaction.tags:
			alias = self.tagAliases.get(tag, None)
			if alias is not None:
				return alias

		alias = self.accountAliases.get(transaction.description, None)
		if alias is not None:
			return alias

		return transaction.description

class IgnoreConfig(CollectionConfig):
	def __init__(self, config):
		self.tags = CollectionConfig.make_set(config['tags'])
		self.accounts = CollectionConfig.make_set(config['accounts'])

class Config:
	def __init__(self, path):
		config = readYaml(path)
		populateConfigRecursively(config, defaultConfig)
		self.since = toDateTime(config['options']['dates']['since'])
		self.until = toDateTime(config['options']['dates']['until'])
		self.limit = config['options']['sources']['up-api']['limit']
		self.ignore = IgnoreConfig(config['ignore'])
		self.income = CollectionConfig(config['collections']['income'])
		self.expense = CollectionConfig(config['collections']['expenses'])
		self.savings = CollectionConfig(config['collections']['savings'])
		self._config = config

		self.income.accounts.add("Interest")

	def filter(self, transactions):
		return filter(lambda t: not isInternalTransaction(t), transactions)

	def classify(self, transaction : GenericTransaction):

		# TODO: Order of classification should be taken from the config
		classifierOrder = {
			self.classify_by_tag,
			self.classify_by_category_presence,
			self.classify_by_account,
			self.classify_by_postive_value,
		}
		for classifier in classifierOrder:
			classification = classifier(transaction)
			if classification is not TransactionType.Unknown:
				return classification

		return TransactionType.Unknown

	def classify_by_tag(self, transaction : GenericTransaction):
		tags = set(transaction.tags)
		if tags.intersection(self.ignore.tags):		return TransactionType.Ignore
		if tags.intersection(self.income.tags):		return TransactionType.Income
		if tags.intersection(self.expense.tags):	return TransactionType.Expense
		if tags.intersection(self.savings.tags):	return TransactionType.Savings
		return TransactionType.Unknown

	def classify_by_account(self, transaction : GenericTransaction):
		account = transaction.description
		if account in self.ignore.accounts:		return TransactionType.Ignore
		if account in self.income.accounts:		return TransactionType.Income
		if account in self.expense.accounts:	return TransactionType.Expense
		if account in self.savings.accounts:	return TransactionType.Savings
		return TransactionType.Unknown

	def classify_by_category_presence(self, transaction : GenericTransaction):
		if transaction.category:
			return TransactionType.Expense
		return TransactionType.Unknown

	def classify_by_postive_value(self, transaction : GenericTransaction):
		if transaction.amount > 0:
			return TransactionType.Income
		return TransactionType.Unknown


defaultClassifier = {
	'tags': [],
	'accounts': [],
}

defaultThreshold = {
	'value': 0,
	'percentage': 0
}

defaultConfig = {
	'options': {
		'output': 'results.txt',
		'dates': {
			'since' : '1 year ago',
			'until': 'today'
		},
		'sources': {
			'up-api' : {
				'token' : 'UP_TOKEN',
				'limit' : 4000,
			}
		}
	},
	'collections' : {
		'income': {
			'name' : 'Income',
			'classifiers' : defaultClassifier,
			'threshold' : defaultThreshold
		},
		'expenses': {
			'name' : 'Expenses',
			'classifiers' : defaultClassifier,
			'threshold' : defaultThreshold
		},
		'savings': {
			'name' : 'Savings',
			'classifiers' : defaultClassifier,
			'threshold' : defaultThreshold
		}
	},
	'ignore': defaultClassifier
}


if __name__ == "__main__":
	config = Config("config/example.yaml")
	print(yaml.dump(config._config))
