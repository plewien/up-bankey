import argparse
import logging as log
import yaml

from os import getenv
from enum import Enum
from datetime import datetime
from dateutil import parser
from dateutil.relativedelta import relativedelta
from typing import Mapping
from upbankapi import NotAuthorizedException

from .protocol import Client


def toDateTime(input: str):
	if input is None:
		return None
	if input in {"today", "now"}:
		return datetime.now()
	if input.endswith("ago"):
		value, unit, _ = input.split()  # assumes format '1 year ago', etc
		if not unit.endswith('s'):
			unit += 's'  # plural necessary
		return datetime.now() - relativedelta(**{unit: int(value)})
	return parser.parse(input)


class TransactionType(Enum):
	Unknown		= 'unknown'
	Ignore		= 'ignore'
	Income		= 'income'
	Expense		= 'expenses'
	Savings		= 'savings'


class ClassifierConfig:
	def __init__(self, config):
		self.collection = {}
		if config is not None:
			for element in config:
				self.add(element)

	def __str__(self):
		return str(self.collection)

	def __repr__(self):
		return repr(self.collection)

	def __bool__(self):
		return self.collection != {}

	def add(self, classification):
		if isinstance(classification, dict):
			self.collection.update(classification)
		else:
			self.collection[classification] = None

	def contains(self, name):
		return name in self.collection

	def get_alias(self, name):
		return self.collection.get(name, None)


class AccountClassifierConfig(ClassifierConfig):
	def contains(self, description):
		# Accounts with a $ prefix are upbank accounts and may have more details in the transaction description
		return super().contains(description) or any(item in description for item in self.collection if item.startswith('$'))


class ThresholdConfig:
	def __init__(self, config):
		self.count = config['count']
		self.absolute = config['value']
		self.relative = config['percentage'] / 100


class CollectionConfig:
	def __init__(self, config):
		self.name = config['name']
		self.tags = ClassifierConfig(config['classifiers']['tags'])
		self.accounts = AccountClassifierConfig(config['classifiers']['accounts'])
		self.threshold = ThresholdConfig(config['threshold'])
		self.outgoing = config['outgoing']

	def __str__(self):
		return "%s(tags=%s, accounts=%s)" % (
			self.name, self.tags, self.accounts)

	def __repr__(self):
		return "%s<name=%r, tags=(%r), accounts=(%r)>" % (
			self.__class__.__name__, self.name, self.tags, self.accounts)


class IgnoreConfig(CollectionConfig):
	def __init__(self, config):
		self.name = "Ignore"
		self.tags = ClassifierConfig(config['tags'])
		self.accounts = AccountClassifierConfig(config['accounts'])


class JointAccountConfig:
	def __init__(self, config):
		self.personal_accounts = AccountClassifierConfig(config['me'])
		self.partner_accounts = AccountClassifierConfig(config['others'])


class UpApiConfig:
	token : str
	limit : int
	pagesize : int
	joint : JointAccountConfig

	def __init__(self, config):
		self.token = getenv(config['token'] if 'token' in config else "UP_TOKEN")
		self.limit = config['limit']
		self.pagesize = config['pagesize']
		if 'joint-account-funders' in config:
			self.joint = JointAccountConfig(config['joint-account-funders'])

	# TODO: Move into interface
	def init_client(self, client_constructor):
		try:
			client = client_constructor(self.token)
			log.info("Authorized: " + client.ping())
			return client
		except NotAuthorizedException:
			log.critical("The token is invalid")
			exit(1)


class Config:
	output : str
	since : datetime
	until : datetime
	collections : Mapping[TransactionType, CollectionConfig]
	up_api : UpApiConfig

	def __init__(self):
		self.args = Config.parser().parse_args()
		config = Config._generate_valid_config(self.args.config)
		self.output = self.args.output if self.args.output else config['options']['output']
		self.since = toDateTime(config['options']['dates']['since'])
		self.until = toDateTime(config['options']['dates']['until'])
		self.up_api = UpApiConfig(config['options']['sources']['up-api'])
		self.collections = {TransactionType.Ignore : IgnoreConfig(config['ignore'])}
		for name, c in config['collections'].items():
			self.collections[TransactionType(name)] = CollectionConfig(c)

		# "Interest" will always be an income stream, so populate here
		self.collections[TransactionType.Income].accounts.add("Interest")
		self.setup_logging()

	@staticmethod
	def parser() -> argparse.ArgumentParser:
		parser = argparse.ArgumentParser(description='Setting the config.')
		parser.add_argument('--config', type=str, default=None, help='Path to config.yaml file')
		parser.add_argument('-o', '--output', type=str, default=None, help='Path to output.txt file')
		parser.add_argument('-v', '--verbose', action="store_true", help='Verbose output')
		return parser
	
	def setup_logging(self):
		if self.args.verbose:
			log.basicConfig(format="%(levelname)s: %(message)s", level=log.DEBUG)
			log.info("Verbose output")
		else:
			log.basicConfig(format="%(levelname)s: %(message)s")

	def __str__(self):
		return 'Dates:\n %s - %s\n' % (self.since, self.until) \
			+ 'Collections:' + '\n'.join(str(collection_config) for collection_config in self.collections.values())

	def print_to_file(self, object):
		with open(self.output, 'w') as f:
			print(object, file=f)

	@staticmethod
	def _generate_valid_config(path):
		with open(path, 'r') as f:
			config = yaml.safe_load(f)
			Config._populate_recursively(config, defaultConfig)
		return config

	# Inspired by https://stackoverflow.com/questions/36831998/how-to-fill-default-parameters-in-yaml-file-using-python
	@staticmethod
	def _populate_recursively(input: dict, default):
		for k in default:
			if isinstance(default[k], dict):  # populate the sub-config
				Config._populate_recursively(input.setdefault(k, {}), default[k])
			else:
				input.setdefault(k, default[k])


defaultClassifier = {
	'tags': [],
	'accounts': [],
}

defaultThreshold = {
	'count': 10,
	'value': 0,
	'percentage': 0
}

defaultConfig = {
	'options': {
		'output': 'results.txt',
		'dates': {
			'since' : '1 year ago',
			'until': 'today'
		}
	},
	'collections' : {
		'income': {
			'name' : 'Income',
			'outgoing' : False,
			'classifiers' : defaultClassifier,
			'threshold' : defaultThreshold
		},
		'expenses': {
			'name' : 'Expenses',
			'outgoing' : True,
			'classifiers' : defaultClassifier,
			'threshold' : defaultThreshold
		},
		'savings': {
			'name' : 'Savings',
			'outgoing' : True,
			'classifiers' : defaultClassifier,
			'threshold' : defaultThreshold
		}
	},
	'ignore': defaultClassifier
}


if __name__ == "__main__":
	print("This is the example config:")
	config = Config("config/example.yaml")
	print(config)
