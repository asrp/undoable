def deepwrap(elem, callbacks=[], undocallbacks=[], wrapper=None, skiproot=False):
    """ Wrap nested list and dict. """
    if wrapper:
        output = wrapper(elem)
        if output is not None:
            return output
    if type(elem) == list:
        inner = [deepwrap(subelem, callbacks, undocallbacks, wrapper)
                 for subelem in elem]
        if skiproot:
            return inner
        return observed_list(inner, callbacks=callbacks, undocallbacks=undocallbacks)
    elif type(elem) == dict:
        inner = dict((key, deepwrap(value, callbacks, undocallbacks, wrapper))
                     for key, value in elem.items())
        if skiproot:
            return inner
        return observed_dict(inner, callbacks=callbacks, undocallbacks=undocallbacks)
    else:
        return elem

class UndoLog(object):
    def __init__(self):
        # self.root: root of the undo tree
        # self.undoroot: root of the current event being treated
        # self.index: marks the position between undo and redo. Always negative
        # (counting from the back).
        self.root = self.undoroot = observed_tree("undo root")
        self.watched = []
        self.index = -1

    def add(self, elem):
        """ Add element to watch. """
        self.watched.append(elem)
        elem.undocallbacks.append(self.log)

    def log(self, elem, undoitem, redoitem):
        if elem.skiplog > 0:
            return
        self.clear_redo()
        self.undoroot.append(observed_tree(name=(elem, undoitem, redoitem)))

    def clear_redo(self):
        if self.undoroot == self.root and self.index > -1:
            # Need to delete everything if we aren't the last index!
            del self.root[self.index+1:]
            self.index = -1

    def start_group(self, name, new_only=False):
        if new_only and self.undoroot.name == name:
            return False
        self.clear_redo()
        self.undoroot.append(observed_tree(name))
        self.index = -1
        self.undoroot = self.undoroot[-1]
        return True

    def end_group(self, name, skip_unstarted=False, delete_if_empty=False):
        if name and self.undoroot.name != name:
            if skip_unstarted: return
            raise Exception("Ending group %s but the current group is %s!" %\
                            (name, self.undoroot.name))
        if not self.undoroot.parent:
            raise Exception("Attempting to end root group!")
        self.undoroot = self.undoroot.parent
        if delete_if_empty and len(self.undoroot) == 0:
            self.undoroot.pop()
        self.index = -1

    def undo(self, node=None):
        if node is None:
            node = self.root[self.index]
            self.index -= 1
        if type(node.name) == str:
            for child in reversed(node):
                self.undo(child)
        else:
            self.unredo_event(node.name[0], node.name[1])

    def redo(self, node=None):
        if node is None:
            node = self.root[self.index + 1]
            self.index += 1
        if type(node.name) == str:
            for child in node:
                self.redo(child)
        else:
            self.unredo_event(node.name[0], node.name[2])

    def unredo_event(self, elem, item):
        elem.skiplog += 1
        getattr(elem, item[0])(*item[1:])
        elem.skiplog -= 1

    def pprint(self, node=None):
        for line in self.pprint_string(node):
            print line

    def pprint_string(self, node=None, indent=0):
        if node is None:
            node = self.root
        if type(node.name) != str:
            yield "%s%s" % (indent*" ", node.name[2][0])
            return
        name = node.name if node.name else ""
        yield "%s%s" % (indent*" ", name)
        for child in node:
            for line in self.pprint_string(child, indent + 2):
                yield line

class observed_list(list):
    """ A list that calls all functions in self.undocallbacks
    with an (undo, redo) pair any time an operation is applied to the list.
    Every function in self.callbacks is called with *redo instead.

    Contains a self.replace function not in python's list for conenience.
    """
    def __init__(self, *args, **kwargs):
        list.__init__(self, *args)
        self.callbacks = kwargs.get("callbacks", [])
        self.undocallbacks = kwargs.get("undocallbacks", [])
        self.skiplog = 0

    def callback(self, undo, redo):
        for callback in self.callbacks:
            callback(self, *redo)
        for callback in self.undocallbacks:
            callback(self, undo, redo)

    def __deepcopy__(self, memo):
        return observed_list(self)

    def __setitem__(self, key, value):
        try:
            oldvalue = self.__getitem__(key)
        except KeyError:
            list.__setitem__(self, key, value)
            self.callback(("__delitem__", key), ("__setitem__", key, value))
        else:
            list.__setitem__(self, key, value)
            self.callback(("__setitem__", key, oldvalue),
                          ("__setitem__", key, value))

    def __delitem__(self, key):
        oldvalue = list.__getitem__(self, key)
        list.__delitem__(self, key)
        self.callback(("__setitem__", key, oldvalue), ("__delitem__", key))

    def __setslice__(self, i, j, sequence):
        oldvalue = list.__getslice__(self, i, j)
        self.callback(("__setslice__", i, j, oldvalue),
                      ("__setslice__", i, j, sequence))
        list.__setslice__(self, i, j, sequence)

    def __delslice__(self, i, j):
        oldvalue = list.__getitem__(self, slice(i, j))
        list.__delslice__(self, i, j)
        self.callback(("__setslice__", i, i, oldvalue), ("__delslice__", i, j))

    def append(self, value):
        list.append(self, value)
        self.callback(("pop",), ("append", value))

    def pop(self, index=-1):
        oldvalue = list.pop(self, index)
        self.callback(("append", oldvalue), ("pop", index))
        return oldvalue

    def extend(self, newvalue):
        oldlen = len(self)
        list.extend(self, newvalue)
        self.callback(("__delslice__", oldlen, len(self)),
                      ("extend", newvalue))

    def insert(self, i, element):
        list.insert(self, i, element)
        self.callback(("pop", i), ("insert", i, element))

    def remove(self, element):
        if element in self:
            oldindex = self.index(element)
        list.remove(self, element)
        self.callback(("insert", oldindex, element), ("remove", element))

    def reverse(self):
        list.reverse(self)
        self.callback(("reverse",), ("reverse",))

    def sort(self, cmpfunc=None):
        oldlist = self[:]
        list.sort(self, cmpfunc)
        self.callback(("replace", oldlist), ("sort",))

    def replace(self, newlist):
        oldlist = self[:]
        self.skiplog += 1
        del self[:]
        try:
            self.extend(newlist)
        except:
            self.replace(oldlist) # Hopefully no infinite loops happens
            self.skiplog -= 1
            raise
        self.skiplog -= 1
        self.callback(("replace", oldlist), ("replace", newlist))

class observed_dict(dict):
    def __init__(self, *args, **kwargs):
        self.callbacks = kwargs.pop("callbacks", [])
        self.undocallbacks = kwargs.pop("undocallbacks", [])
        dict.__init__(self, *args, **kwargs)
        self.skiplog = 0

    def callback(self, undo, redo):
        for callback in self.callbacks:
            callback(self, *redo)
        for callback in self.undocallbacks:
            callback(self, undo, redo)

    def __deepcopy__(self, memo):
        return observed_dict(self)

    def __setitem__(self, key, value):
        try:
            oldvalue = self.__getitem__(key)
        except KeyError:
            dict.__setitem__(self, key, value)
            self.callback(("__delitem__", key), ("__setitem__", key, value))
        else:
            dict.__setitem__(self, key, value)
            self.callback(("__setitem__", key, oldvalue),
                          ("__setitem__", key, value))

    def __delitem__(self, key):
        oldvalue = self[key]
        dict.__delitem__(self, key)
        self.callback(("__setitem__", key, oldvalue), ("__delitem__", key))

    def clear(self):
        oldvalue = self.copy()
        dict.clear(self)
        self.callback(("update", oldvalue), ("clear",))

    def update(self, update_dict):
        oldvalue = self.copy()
        dict.update(self, update_dict)
        self.callback(("replace", oldvalue), ("update", update_dict))

    def setdefault(self, key, value=None):
        if key not in self:
            dict.setdefault(self, key, value)
            self.callback(("__delitem__", key), ("setdefault", key, value))
            return value
        else:
            return self[key]

    def pop(self, key, default=None):
        if key in self:
            value = dict.pop(self, key, default)
            self.callback(("__setitem__", key, value), ("pop", key, default))
            return value
        else:
            return default

    def popitem(self):
        key, value = dict.popitem(self)
        self.callback(("__setitem__", key, default), ("popitem",))
        return key, value

    def replace(self, newdict):
        oldvalue = self.copy()
        self.skiplog += 1
        self.clear()
        try:
            self.update(newdict)
        except:
            self.replace(oldvalue) # Hopefully no infinite loops happens
            self.skiplog -= 1
            raise
        self.skiplog -= 1
        self.callback(("replace", newdict), ("replace", oldvalue))

class observed_tree(list):
    """ An ordered list of children. The only difference with list is a maintained parent pointer. All elements of this list are expected to be trees or have parent pointers and a reparent function.

    Expects to contain at most one copy of any elements.

    Can be used to model XML, JSON documents, DOM, etc."""
    def __init__(self, name=None, value=[], parent=None,
                 callbacks=None, undocallbacks=None):
        list.__init__(self, value)
        self.parent = parent
        self.name = name
        self.callbacks = callbacks if callbacks else []
        self.undocallbacks = undocallbacks if undocallbacks else []
        self.skiplog = 0

    def callback(self, undo, redo, origin=None):
        # TODO: Need to think of a better way to pass self along
        if origin == None:
            origin = self
        for callback in self.callbacks:
            callback(origin, *redo)
        for callback in self.undocallbacks:
            callback(origin, undo, redo)
        if self.parent:
            self.parent.callback(undo, redo, origin)

    def _reparent(self, newparent, remove=False):
        if remove and self.parent:
            self.parent.remove(self, reparent=False)
        self.parent = newparent

    def __setitem__(self, key, value):
        try:
            oldvalue = self.__getitem__(key)
        except KeyError:
            value._reparent(self, True)
            list.__setitem__(self, key, value)
            # What to do about undo on that reparent
            self.callback(("__delitem__", key), ("__setitem__", key, value))
        else:
            oldvalue._reparent(None)
            value._reparent(self, True)
            list.__setitem__(self, key, value)
            self.callback(("__setitem__", key, oldvalue),
                          ("__setitem__", key, value))

    def __delitem__(self, key):
        oldvalue = list.__getitem__(self, key)
        list.__delitem__(self, key)
        oldvalue._reparent(None)
        # What to do about undo on that reparent?
        # __setitem__ takes care of this at the moment.
        self.callback(("__setitem__", key, oldvalue), ("__delitem__", key))

    def __setslice__(self, i, j, sequence):
        oldvalue = list.__getslice__(self, i, j)
        self.callback(("__setslice__", i, j, oldvalue),
                      ("__setslice__", i, j, sequence))
        for child in oldvalue:
            child._reparent(None, True)
        for child in sequence:
            child._reparent(self, True)
        list.__setslice__(self, i, j, sequence)

    def __delslice__(self, i, j):
        oldvalue = list.__getitem__(self, slice(i, j))
        for child in oldvalue:
            child._reparent(None, True)
        list.__delslice__(self, i, j)
        self.callback(("__setslice__", i, i, oldvalue), ("__delslice__", i, j))

    def __eq__(self, other):
        return self is other

    def append(self, value):
        list.append(self, value)
        value._reparent(self, True)
        self.callback(("pop",), ("append", value))

    def pop(self, index=-1):
        oldvalue = list.pop(self, index)
        oldvalue._reparent(None)
        self.callback(("append", oldvalue), ("pop", index))
        return oldvalue

    def extend(self, newvalue):
        oldlen = len(self)
        list.extend(self, newvalue)
        newvalue = newvalue[:]
        for value in newvalue:
            value._reparent(self, True)
        self.callback(("__delslice__", oldlen, len(self)),
                      ("extend", newvalue))

    def insert(self, i, element):
        element._reparent(self, True)
        list.insert(self, i, element)
        self.callback(("pop", i), ("insert", i, element))

    def remove(self, element, reparent=True):
        if element in self:
            oldindex = self.index(element)
        list.remove(self, element)
        if reparent:
            element._reparent(None)
        self.callback(("insert", oldindex, element), ("remove", element))

    def reverse(self):
        list.reverse(self)
        self.callback(("reverse",), ("reverse",))

    def sort(self, cmpfunc=None):
        list.sort(self, cmpfunc)
        self.callback(("replace", oldlist), ("sort",))

    def replace(self, newlist):
        oldlist = self[:]
        self.skiplog += 1
        del self[:]
        try:
            self.extend(newlist)
        except:
            self.replace(oldlist) # Hopefully no infinite loops happens
            self.skiplog -= 1
            raise
        self.skiplog -= 1
        self.callback(("replace", oldlist), ("replace", newlist))

    # Helper functions. Maybe they should be elsewhere.
    def tops(self, condition):
        """ Return the top (incomparable maximal) anti-chain amongst descendants of widget that satisfy condition"""
        for child in self:
            if condition(child):
                yield child
            else:
                for gc in child.tops(condition):
                    yield gc

    @property
    def descendants(self):
        for child in self:
            for gc in child.descendants:
                yield gc
            yield child

# Add this to callbacks for debugging
def printargs(*args):
    print args

if __name__ == '__main__':
    # minimal demonstration
    u = UndoLog()
    d = observed_dict({1: "one", 2: "two"})
    l = observed_list([1, 2, 3])
    u.add(d)
    u.add(l)
    l.append(1)
    d[3] = "Hello"
    u.start_group("foo")
    d[53] = "user"
    del d[1]
    u.end_group("foo")
    u.start_group("foo")
    d["bar"] = "baz"
    u.end_group("foo")
    deep = {"abc": "def", "alist": [1, 2, 3]}
    obs_deep = deepwrap(deep, undocallbacks=[u.log])
    u.watched.append(obs_deep)
    obs_deep["d"] = "e"
    obs_deep["alist"].append(4)
    # Now run multiple u.undo(), u.redo()
