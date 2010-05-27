"""
This module contains the container classes to create objects
that persist directly in a Redis server.
"""

import collections
from functools import partial
from connection import _get_client


class Container(object):
    """Create a container object saved in Redis.

    Arguments:
        key -- the Redis key this container is stored at
        db  -- the Redis client object. Default: None

    When ``db`` is not set, the gets the default connection from
    ``redisco.connection`` module.
    """

    def __init__(self, key, db=None):
        if db is None:
            self.db = _get_client()
        else:
            self.db = db
        self.key = key

    def clear(self):
        """Remove container from Redis database."""
        del self.db[self.key]

    def __getattribute__(self, att):
        if att in object.__getattribute__(self, 'DELEGATEABLE_METHODS'):
            return partial(getattr(object.__getattribute__(self, 'db'), att), self.key)
        else:
            return object.__getattribute__(self, att)

    DELEGATEABLE_METHODS = ()


class Set(Container):
    """A set stored in Redis."""

    def add(self, value):
        """Add the specified member to the Set."""
        self.sadd(value)

    def remove(self, value):
        """Remove the value from the redis set."""
        if not self.srem(value):
            raise KeyError, value
        
    def pop(self):
        """Remove and return (pop) a random element from the Set."""
        return self.spop()

    def discard(self, value):
        """Remove element elem from the set if it is present."""
        self.srem(value)

    def __len__(self):
        """Return the cardinality of set."""
        return self.scard()

    def __repr__(self):
        return "<%s '%s' %s>" % (self.__class__.__name__, self.key,
                self.members)

    # TODO: Note, the elem argument to the __contains__(), remove(),
    #       and discard() methods may be a set
    def __contains__(self, value):
        return self.sismember(value)

    def isdisjoint(self, other):
        """Return True if the set has no elements in common with other."""
        return not bool(self.db.sinter([self.key, other.key]))

    def issubset(self, other):
        """Test whether every element in the set is in other."""
        return self <= other

    def __le__(self, other):
        return self.db.sinter([self.key, other.key]) == self.all()

    def __lt__(self, other):
        """Test whether the set is a true subset of other."""
        return self <= other and self != other

    def __eq__(self, other):
        if other.key == self.key:
            return True
        slen, olen = len(self), len(other)
        if olen == slen:
            return self.members == other.members
        else:
            return False

    def issuperset(self, other):
        """Test whether every element in other is in the set."""
        return self >= other

    def __ge__(self, other):
        """Test whether every element in other is in the set."""
        return self.db.sinter([self.key, other.key]) == other.all()
    
    def __gt__(self, other):
        """Test whether the set is a true superset of other."""
        return self >= other and self != other


    # SET Operations
    def union(self, key, *others):
        """Return a new set with elements from the set and all others."""
        if not isinstance(key, str):
            raise ValueError("String expected.")
        self.db.sunionstore(key, [self.key] + [o.key for o in others])
        return Set(key)

    def intersection(self, key, *others):
        """Return a new set with elements common to the set and all others."""
        if not isinstance(key, str):
            raise ValueError("String expected.")
        self.db.sinterstore(key, [self.key] + [o.key for o in others])
        return Set(key)

    def difference(self, key, *others):
        """Return a new set with elements in the set that are not in the others."""
        if not isinstance(key, str):
            raise ValueError("String expected.")
        self.db.sdiffstore(key, [self.key] + [o.key for o in others])
        return Set(key)

    def update(self, *others):
        """Update the set, adding elements from all others."""
        self.db.sunionstore(self.key, [self.key] + [o.key for o in others])

    def __ior__(self, other):
        self.db.sunionstore(self.key, [self.key, other.key])
        return self

    def intersection_update(self, *others):
        """Update the set, keeping only elements found in it and all others."""
        self.db.sinterstore(self.key, [o.key for o in [self.key] + others])

    def __iand__(self, other):
        self.db.sinterstore(self.key, [self.key, other.key])
        return self

    def difference_update(self, *others):
        """Update the set, removing elements found in others."""
        self.db.sdiffstore(self.key, [o.key for o in [self.key] + others])
        
    def __isub__(self, other):
        self.db.sdiffstore(self.key, [self.key, other.key])
        return self
    
    def __repr__(self):
        return u"<redisco.containers.Set(key=%s)>" % self.key

    def all(self):
        return self.db.smembers(self.key)
    members = property(all)

    def copy(self, key):
        """Copy the set to another key and return the new Set.

        WARNING: If the key exists, it overwrites it.
        """
        copy = Set(key=key, db=self.db)
        copy.clear()
        copy |= self
        return copy

    def __iter__(self):
        return self.members.__iter__()

    DELEGATEABLE_METHODS = ('sadd', 'srem', 'spop', 'smembers',
            'scard', 'sismember', 'srandmember')


class List(Container):

    def all(self):
        """Returns all items in the list."""
        return self.lrange(0, -1)
    members = property(all)

    def __len__(self):
        return self.llen()

    def __getitem__(self, index):
        if isinstance(index, int):
            return self.lindex(index)
        elif isinstance(index, slice):
            indices = index.indices(len(self))
            return self.lrange(indices[0], indices[1])
        else:
            raise TypeError

    def __setitem__(self, index, value):
        self.lset(index, value)

    def append(self, value):
        """Append the value to the list."""
        self.rpush(value)
    push = append

    def extend(self, iterable):
        """Extend list by appending elements from the iterable."""
        map(lambda i: self.rpush(i), iterable)

    def count(self, value):
        """Return number of occurrences of value."""
        return self.members.count(value)

    def index(self, value):
        """Return first index of value."""
        return self.all().index(value)

    def pop(self):
        """Remove and return the last item"""
        return self.rpop()

    def shift(self):
        """Remove and return the first item."""
        return self.lpop()

    def unshift(self, value):
        """Add an element at the beginning of the list."""
        self.lpush(value)

    def remove(self, value, num=1):
        """Remove first occurrence of value."""
        self.lrem(value, num)

    def reverse(self):
        """Reverse in place."""
        r = self[:]
        r.reverse()
        self.clear()
        self.extend(r)

    def copy(self, key):
        """Copy the list to a new list.

        WARNING: If key exists, it clears it before copying.
        """
        copy = List(key, self.db)
        copy.clear()
        copy.extend(self)
        return copy

    def trim(self, start, end):
        """Trim the list from start to end."""
        self.ltrim(start, end)

    def __iter__(self):
        return self.members.__iter__()

    def __repr__(self):
        return "<%s '%s' %s>" % (self.__class__.__name__, self.key,
                self.members)

    DELEGATEABLE_METHODS = ('lrange', 'lpush', 'rpush', 'llen',
            'ltrim', 'lindex', 'lset', 'lpop', 'lrem', 'rpop',)

class SortedSet(Container):

    def add(self, member, score):
        """Adds member to the set."""
        self.zadd(member, score)

    def remove(self, member):
        """Removes member from set."""
        self.zrem(member)

    def incr_by(self, member, increment):
        """Increments the member by increment."""
        self.zincrby(member, increment)

    def rank(self, member):
        """Return the rank (the index) of the element."""
        return self.zrank(member)

    def revrank(self, member):
        """Return the rank of the member in reverse order."""
        return self.zrevrank(member)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return self.zrange(index.start, index.stop)
        else:
            return self.zrange(index, index)[0]

    def score(self, member):
        """Returns the score of member."""
        return self.zscore(member)

    def __len__(self):
        return self.zcard()

    def __contains__(self, val):
        return self.zscore(val) is not None

    @property
    def members(self):
        """Returns the members of the set."""
        return self.zrange(0, -1)

    def __iter__(self):
        return self.members.__iter__()

    def __repr__(self):
        return "<%s '%s' %s>" % (self.__class__.__name__, self.key,
                self.members)

    @property
    def _min_score(self):
        return self.zscore(self.__getitem__(0))

    @property
    def _max_score(self):
        return self.zscore(self.__getitem__(-1))

    def lt(self, v, limit=None, offset=None):
        """Returns the list of the members of the set that have scores
        less than v.
        """
        if limit is not None and offset is None:
            offset = 0
        return self.zrangebyscore(self._min_score, "(%f" % v,
                start=offset, num=limit)

    def le(self, v, limit=None, offset=None):
        """Returns the list of the members of the set that have scores
        less than or equal to v.
        """
        if limit is not None and offset is None:
            offset = 0
        return self.zrangebyscore(self._min_score, v,
                start=offset, num=limit)

    def gt(self, v, limit=None, offset=None):
        """Returns the list of the members of the set that have scores
        greater than v.
        """
        if limit is not None and offset is None:
            offset = 0
        return self.zrangebyscore("(%f" % v, self._max_score,
                start=offset, num=limit)

    def ge(self, v, limit=None, offset=None):
        """Returns the list of the members of the set that have scores
        greater than or equal to v.
        """
        if limit is not None and offset is None:
            offset = 0
        return self.zrangebyscore("(%f" % v, self._max_score,
                start=offset, num=limit)

    def between(self, min, max, limit=None, offset=None):
        """Returns the list of the members of the set that have scores
        between min and max.
        """
        if limit is not None and offset is None:
            offset = 0
        return self.zrangebyscore(min, max,
                start=offset, num=limit)

    def eq(self, value):
        """Returns the list of the members of the set that have scores
        equal to value.
        """
        return self.zrangebyscore(value, value)

    DELEGATEABLE_METHODS = ('zadd', 'zrem', 'zincrby', 'zrank',
            'zrevrank', 'zrange', 'zrangebyscore', 'zcard',
            'zscore', 'zremrangebyrank', 'zremrangebyscore')


class NonPersistentList(object):
    def __init__(self, l):
        self._list = l

    @property
    def members(self):
        return self._list

    def __iter__(self):
        return iter(self.members)

    def __len__(self):
        return len(self._list)


class Hash(Container, collections.MutableMapping):

    def __getitem__(self, att):
        return self.hget(att)

    def __setitem__(self, att, val):
        self.hset(att, val)

    def __delitem__(self, att):
        self.hdel(att)

    def __len__(self):
        return self.hlen()

    def __iter__(self):
        return self.hgetall().__iter__()

    def __contains__(self, att):
        return self.hexists(att)

    def __repr__(self):
        return "<%s '%s' %s>" % (self.__class__.__name__, self.key, self.hgetall())

    def keys(self):
        return self.hkeys()

    def values(self):
        return self.hvals()

    @property
    def dict(self):
        return self.hgetall()

    DELEGATEABLE_METHODS = ('hlen', 'hset', 'hdel', 'hkeys',
            'hgetall', 'hvals', 'hget', 'hexists', 'hincrby',
            'hmget', 'hmset')
