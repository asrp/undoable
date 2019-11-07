# Undoable

A simple Python list (`observed_list`) and dict (`observed_dict`) with callbacks when they are changed and undo/redo using these callbacks.

Also includes `observed_tree`, a labelled tree with ordered children implemented as Python list with parent pointers and a bit of consistency check.

## Implementation

Implemented using the [command pattern](https://en.wikipedia.org/wiki/Command_pattern). See [my blog post discussing this](https://asrp.github.io/blog/undo-redo.html).

## Example

```
git clone https://github.com/asrp/undoable
cd undoable
```

### Callbacks

```python
>>> from undoable import observed_dict, observed_list
>>> def printargs(*args):
...     print(args)
...
>>> l = observed_list([1, 2, 3])
>>> l.callbacks.append(printargs)
>>> l.append(4)
([1, 2, 3, 4], 'append', 4)
>>> l.extend([5, 6, 7])
([1, 2, 3, 4, 5, 6, 7], 'extend', [5, 6, 7])
>>> d = observed_dict({1: "one", 2: "two"})
>>> d.callbacks.append(printargs)
>>> d[3] = "three"
({1: 'one', 2: 'two', 3: 'three'}, '__setitem__', 3, 'three')
>>> d2 = observed_dict()
>>> d2.undocallbacks.append(printargs)
>>> d2[1] = "one"
({1: 'one'}, ('__delitem__', 1), ('__setitem__', 1, 'one'))
```

### Undo/redo

```python
>>> from undoable import UndoLog, observed_dict, observed_list
>>> u = UndoLog()
>>> d = observed_dict({1: "one", 2: "two"})
>>> l = observed_list([1, 2, 3])
>>> u.add(d)
>>> u.add(l)
>>> l.append(1)
>>> d[3] = "Hello"
>>> l
[1, 2, 3, 1]
>>> d
{1: 'one', 2: 'two', 3: 'Hello'}
>>> u.undo()
>>> d
{1: 'one', 2: 'two'}
>>> u.undo()
>>> l
[1, 2, 3]
>>> u.redo()
>>> u.redo()
>>> l
[1, 2, 3, 1]
>>> d
{1: 'one', 2: 'two', 3: 'Hello'}
>>> u.start_group("foo")
True
>>> d[53] = "user"
>>> del d[1]
>>> u.end_group("foo")
>>> d
{2: 'two', 3: 'Hello', 53: 'user'}
>>> u.undo()
>>> d
{1: 'one', 2: 'two', 3: 'Hello'}
```
