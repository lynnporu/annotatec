<p align="center">
  <img src="https://github.com/lynnporu/annotatec/raw/dev/logo.png">
</p>

[![PyPI](https://img.shields.io/pypi/v/annotatec.svg)](https://pypi.python.org/pypi/annotatec)
![GitHub repo size](https://img.shields.io/github/repo-size/lynnporu/annotatec)
![GitHub](https://img.shields.io/github/license/lynnporu/annotatec)

------------

**annotatec** helps you create Python packages with C embeddings.

Imagine you're developing C library and already have more than 50 functions. Sometimes you change signatures of old functions or rename them. It'll be headache to write and support all [ctypes](https://docs.python.org/3/library/ctypes.html)-declarations for Python wrapper. **annotatec** will create all Python objects for you. All you need is to provide declarations, which can be placed directly into your C code.

## Minimal livable example

You have some library `lib.c` and it's header `lib.h`. These files were compiled into `lib.so` (or `lib.dll` in Windows).

`lib.c` source:
```c
#include "lib.h"
int sum(int a, short b, long long c) { return a + b + c; }
```

`lib.h` source:
```c
/* @function sum
 * @return int
 * @argument int
 * @argument short
 * @argument longlong
 */
int sum(int, short, long long);
```

Here's a Python wrapper:
```python
import annotatec

libc = annotatec.Loader(
    library="lib.so", headers=["lib.h"])
```

That's all! Now you can test it like so:
```python
>>> libc.sum(1, 2, 3)
<<< 6
```
## Reference

Read detailed reference in [wiki](https://github.com/lynnporu/annotatec/wiki)-pages.
