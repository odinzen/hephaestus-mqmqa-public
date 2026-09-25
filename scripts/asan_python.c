/* Python launcher for the AddressSanitizer debug build (scripts/build_asan.sh).
 * It loads the ASan runtime before the interpreter starts, so every heap block
 * Python allocates is owned by ASan. A runtime that arrives later with mqmqa.dll
 * meets blocks it did not allocate and reports false errors on realloc and free. */
#include <stdio.h>
#include <windows.h>

typedef int (*py_main_fn)(int, wchar_t **);

int wmain(int argc, wchar_t **argv)
{
    if (!LoadLibraryW(L"clang_rt.asan_dynamic-x86_64.dll")) {
        fprintf(stderr, "cannot load the ASan runtime\n");
        return 90;
    }
    HMODULE py = LoadLibraryW(PYDLL);
    if (!py) {
        fprintf(stderr, "cannot load %ls (is the Python env on PATH?)\n", PYDLL);
        return 91;
    }
    py_main_fn py_main = (py_main_fn)GetProcAddress(py, "Py_Main");
    return py_main ? py_main(argc, argv) : 92;
}
