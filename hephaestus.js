var Hephaestus = (() => {
  var _scriptName = typeof document != 'undefined' ? document.currentScript?.src : undefined;
  return (
async function(moduleArg = {}) {
  var moduleRtn;

// include: shell.js
// The Module object: Our interface to the outside world. We import
// and export values on it. There are various ways Module can be used:
// 1. Not defined. We create it here
// 2. A function parameter, function(moduleArg) => Promise<Module>
// 3. pre-run appended it, var Module = {}; ..generated code..
// 4. External script tag defines var Module.
// We need to check if Module already exists (e.g. case 3 above).
// Substitution will be replaced with actual code on later stage of the build,
// this way Closure Compiler will not mangle it (e.g. case 4. above).
// Note that if you want to run closure, and also to use Module
// after the generated code, you will need to define   var Module = {};
// before the code. Then that object will be used in the code, and you
// can continue to use Module afterwards as well.
var Module = moduleArg;

// Set up the promise that indicates the Module is initialized
var readyPromiseResolve, readyPromiseReject;
var readyPromise = new Promise((resolve, reject) => {
  readyPromiseResolve = resolve;
  readyPromiseReject = reject;
});

// Determine the runtime environment we are in. You can customize this by
// setting the ENVIRONMENT setting at compile time (see settings.js).

// Attempt to auto-detect the environment
var ENVIRONMENT_IS_WEB = typeof window == 'object';
var ENVIRONMENT_IS_WORKER = typeof WorkerGlobalScope != 'undefined';
// N.b. Electron.js environment is simultaneously a NODE-environment, but
// also a web environment.
var ENVIRONMENT_IS_NODE = typeof process == 'object' && process.versions?.node && process.type != 'renderer';
var ENVIRONMENT_IS_SHELL = !ENVIRONMENT_IS_WEB && !ENVIRONMENT_IS_NODE && !ENVIRONMENT_IS_WORKER;

if (ENVIRONMENT_IS_NODE) {

}

// --pre-jses are emitted after the Module integration code, so that they can
// refer to Module (if they choose; they can also define Module)


var arguments_ = [];
var thisProgram = './this.program';
var quit_ = (status, toThrow) => {
  throw toThrow;
};

if (typeof __filename != 'undefined') { // Node
  _scriptName = __filename;
} else
if (ENVIRONMENT_IS_WORKER) {
  _scriptName = self.location.href;
}

// `/` should be present at the end if `scriptDirectory` is not empty
var scriptDirectory = '';
function locateFile(path) {
  if (Module['locateFile']) {
    return Module['locateFile'](path, scriptDirectory);
  }
  return scriptDirectory + path;
}

// Hooks that are implemented differently in different runtime environments.
var readAsync, readBinary;

if (ENVIRONMENT_IS_NODE) {
  const isNode = typeof process == 'object' && process.versions?.node && process.type != 'renderer';
  if (!isNode) throw new Error('not compiled for this environment (did you build to HTML and try to run it not on the web, or set ENVIRONMENT to something - like node - and run it someplace else - like on the web?)');

  var nodeVersion = process.versions.node;
  var numericVersion = nodeVersion.split('.').slice(0, 3);
  numericVersion = (numericVersion[0] * 10000) + (numericVersion[1] * 100) + (numericVersion[2].split('-')[0] * 1);
  var minVersion = 160000;
  if (numericVersion < 160000) {
    throw new Error('This emscripten-generated code requires node v16.0.0 (detected v' + nodeVersion + ')');
  }

  // These modules will usually be used on Node.js. Load them eagerly to avoid
  // the complexity of lazy-loading.
  var fs = require('fs');
  var nodePath = require('path');

  scriptDirectory = __dirname + '/';

// include: node_shell_read.js
readBinary = (filename) => {
  // We need to re-wrap `file://` strings to URLs.
  filename = isFileURI(filename) ? new URL(filename) : filename;
  var ret = fs.readFileSync(filename);
  assert(Buffer.isBuffer(ret));
  return ret;
};

readAsync = async (filename, binary = true) => {
  // See the comment in the `readBinary` function.
  filename = isFileURI(filename) ? new URL(filename) : filename;
  var ret = fs.readFileSync(filename, binary ? undefined : 'utf8');
  assert(binary ? Buffer.isBuffer(ret) : typeof ret == 'string');
  return ret;
};
// end include: node_shell_read.js
  if (process.argv.length > 1) {
    thisProgram = process.argv[1].replace(/\\/g, '/');
  }

  arguments_ = process.argv.slice(2);

  quit_ = (status, toThrow) => {
    process.exitCode = status;
    throw toThrow;
  };

} else
if (ENVIRONMENT_IS_SHELL) {

  const isNode = typeof process == 'object' && process.versions?.node && process.type != 'renderer';
  if (isNode || typeof window == 'object' || typeof WorkerGlobalScope != 'undefined') throw new Error('not compiled for this environment (did you build to HTML and try to run it not on the web, or set ENVIRONMENT to something - like node - and run it someplace else - like on the web?)');

} else

// Note that this includes Node.js workers when relevant (pthreads is enabled).
// Node.js workers are detected as a combination of ENVIRONMENT_IS_WORKER and
// ENVIRONMENT_IS_NODE.
if (ENVIRONMENT_IS_WEB || ENVIRONMENT_IS_WORKER) {
  try {
    scriptDirectory = new URL('.', _scriptName).href; // includes trailing slash
  } catch {
    // Must be a `blob:` or `data:` URL (e.g. `blob:http://site.com/etc/etc`), we cannot
    // infer anything from them.
  }

  if (!(typeof window == 'object' || typeof WorkerGlobalScope != 'undefined')) throw new Error('not compiled for this environment (did you build to HTML and try to run it not on the web, or set ENVIRONMENT to something - like node - and run it someplace else - like on the web?)');

  {
// include: web_or_worker_shell_read.js
if (ENVIRONMENT_IS_WORKER) {
    readBinary = (url) => {
      var xhr = new XMLHttpRequest();
      xhr.open('GET', url, false);
      xhr.responseType = 'arraybuffer';
      xhr.send(null);
      return new Uint8Array(/** @type{!ArrayBuffer} */(xhr.response));
    };
  }

  readAsync = async (url) => {
    // Fetch has some additional restrictions over XHR, like it can't be used on a file:// url.
    // See https://github.com/github/fetch/pull/92#issuecomment-140665932
    // Cordova or Electron apps are typically loaded from a file:// url.
    // So use XHR on webview if URL is a file URL.
    if (isFileURI(url)) {
      return new Promise((resolve, reject) => {
        var xhr = new XMLHttpRequest();
        xhr.open('GET', url, true);
        xhr.responseType = 'arraybuffer';
        xhr.onload = () => {
          if (xhr.status == 200 || (xhr.status == 0 && xhr.response)) { // file URLs can return 0
            resolve(xhr.response);
            return;
          }
          reject(xhr.status);
        };
        xhr.onerror = reject;
        xhr.send(null);
      });
    }
    var response = await fetch(url, { credentials: 'same-origin' });
    if (response.ok) {
      return response.arrayBuffer();
    }
    throw new Error(response.status + ' : ' + response.url);
  };
// end include: web_or_worker_shell_read.js
  }
} else
{
  throw new Error('environment detection error');
}

var out = console.log.bind(console);
var err = console.error.bind(console);

var IDBFS = 'IDBFS is no longer included by default; build with -lidbfs.js';
var PROXYFS = 'PROXYFS is no longer included by default; build with -lproxyfs.js';
var WORKERFS = 'WORKERFS is no longer included by default; build with -lworkerfs.js';
var FETCHFS = 'FETCHFS is no longer included by default; build with -lfetchfs.js';
var ICASEFS = 'ICASEFS is no longer included by default; build with -licasefs.js';
var JSFILEFS = 'JSFILEFS is no longer included by default; build with -ljsfilefs.js';
var OPFS = 'OPFS is no longer included by default; build with -lopfs.js';

var NODEFS = 'NODEFS is no longer included by default; build with -lnodefs.js';

// perform assertions in shell.js after we set up out() and err(), as otherwise
// if an assertion fails it cannot print the message

assert(!ENVIRONMENT_IS_SHELL, 'shell environment detected but not enabled at build time.  Add `shell` to `-sENVIRONMENT` to enable.');

// end include: shell.js

// include: preamble.js
// === Preamble library stuff ===

// Documentation for the public APIs defined in this file must be updated in:
//    site/source/docs/api_reference/preamble.js.rst
// A prebuilt local version of the documentation is available at:
//    site/build/text/docs/api_reference/preamble.js.txt
// You can also build docs locally as HTML or other formats in site/
// An online HTML version (which may be of a different version of Emscripten)
//    is up at http://kripken.github.io/emscripten-site/docs/api_reference/preamble.js.html

var wasmBinary;

if (typeof WebAssembly != 'object') {
  err('no native wasm support detected');
}

// Wasm globals

var wasmMemory;

//========================================
// Runtime essentials
//========================================

// whether we are quitting the application. no code should run after this.
// set in exit() and abort()
var ABORT = false;

// set by exit() and abort().  Passed to 'onExit' handler.
// NOTE: This is also used as the process return code code in shell environments
// but only when noExitRuntime is false.
var EXITSTATUS;

// In STRICT mode, we only define assert() when ASSERTIONS is set.  i.e. we
// don't define it at all in release modes.  This matches the behaviour of
// MINIMAL_RUNTIME.
// TODO(sbc): Make this the default even without STRICT enabled.
/** @type {function(*, string=)} */
function assert(condition, text) {
  if (!condition) {
    abort('Assertion failed' + (text ? ': ' + text : ''));
  }
}

// We used to include malloc/free by default in the past. Show a helpful error in
// builds with assertions.

// Memory management

var HEAP,
/** @type {!Int8Array} */
  HEAP8,
/** @type {!Uint8Array} */
  HEAPU8,
/** @type {!Int16Array} */
  HEAP16,
/** @type {!Uint16Array} */
  HEAPU16,
/** @type {!Int32Array} */
  HEAP32,
/** @type {!Uint32Array} */
  HEAPU32,
/** @type {!Float32Array} */
  HEAPF32,
/* BigInt64Array type is not correctly defined in closure
/** not-@type {!BigInt64Array} */
  HEAP64,
/* BigUint64Array type is not correctly defined in closure
/** not-t@type {!BigUint64Array} */
  HEAPU64,
/** @type {!Float64Array} */
  HEAPF64;

var runtimeInitialized = false;

/**
 * Indicates whether filename is delivered via file protocol (as opposed to http/https)
 * @noinline
 */
var isFileURI = (filename) => filename.startsWith('file://');

// include: runtime_shared.js
// include: runtime_stack_check.js
// Initializes the stack cookie. Called at the startup of main and at the startup of each thread in pthreads mode.
function writeStackCookie() {
  var max = _emscripten_stack_get_end();
  assert((max & 3) == 0);
  // If the stack ends at address zero we write our cookies 4 bytes into the
  // stack.  This prevents interference with SAFE_HEAP and ASAN which also
  // monitor writes to address zero.
  if (max == 0) {
    max += 4;
  }
  // The stack grow downwards towards _emscripten_stack_get_end.
  // We write cookies to the final two words in the stack and detect if they are
  // ever overwritten.
  HEAPU32[((max)>>2)] = 0x02135467;
  HEAPU32[(((max)+(4))>>2)] = 0x89BACDFE;
  // Also test the global address 0 for integrity.
  HEAPU32[((0)>>2)] = 1668509029;
}

function checkStackCookie() {
  if (ABORT) return;
  var max = _emscripten_stack_get_end();
  // See writeStackCookie().
  if (max == 0) {
    max += 4;
  }
  var cookie1 = HEAPU32[((max)>>2)];
  var cookie2 = HEAPU32[(((max)+(4))>>2)];
  if (cookie1 != 0x02135467 || cookie2 != 0x89BACDFE) {
    abort(`Stack overflow! Stack cookie has been overwritten at ${ptrToString(max)}, expected hex dwords 0x89BACDFE and 0x2135467, but received ${ptrToString(cookie2)} ${ptrToString(cookie1)}`);
  }
  // Also test the global address 0 for integrity.
  if (HEAPU32[((0)>>2)] != 0x63736d65 /* 'emsc' */) {
    abort('Runtime error: The application has corrupted its heap memory area (address zero)!');
  }
}
// end include: runtime_stack_check.js
// include: runtime_exceptions.js
// end include: runtime_exceptions.js
// include: runtime_debug.js
var runtimeDebug = true; // Switch to false at runtime to disable logging at the right times

// Used by XXXXX_DEBUG settings to output debug messages.
function dbg(...args) {
  if (!runtimeDebug && typeof runtimeDebug != 'undefined') return;
  // TODO(sbc): Make this configurable somehow.  Its not always convenient for
  // logging to show up as warnings.
  console.warn(...args);
}

// Endianness check
(() => {
  var h16 = new Int16Array(1);
  var h8 = new Int8Array(h16.buffer);
  h16[0] = 0x6373;
  if (h8[0] !== 0x73 || h8[1] !== 0x63) throw 'Runtime error: expected the system to be little-endian! (Run with -sSUPPORT_BIG_ENDIAN to bypass)';
})();

function consumedModuleProp(prop) {
  if (!Object.getOwnPropertyDescriptor(Module, prop)) {
    Object.defineProperty(Module, prop, {
      configurable: true,
      set() {
        abort(`Attempt to set \`Module.${prop}\` after it has already been processed.  This can happen, for example, when code is injected via '--post-js' rather than '--pre-js'`);

      }
    });
  }
}

function ignoredModuleProp(prop) {
  if (Object.getOwnPropertyDescriptor(Module, prop)) {
    abort(`\`Module.${prop}\` was supplied but \`${prop}\` not included in INCOMING_MODULE_JS_API`);
  }
}

// forcing the filesystem exports a few things by default
function isExportedByForceFilesystem(name) {
  return name === 'FS_createPath' ||
         name === 'FS_createDataFile' ||
         name === 'FS_createPreloadedFile' ||
         name === 'FS_unlink' ||
         name === 'addRunDependency' ||
         // The old FS has some functionality that WasmFS lacks.
         name === 'FS_createLazyFile' ||
         name === 'FS_createDevice' ||
         name === 'removeRunDependency';
}

/**
 * Intercept access to a global symbol.  This enables us to give informative
 * warnings/errors when folks attempt to use symbols they did not include in
 * their build, or no symbols that no longer exist.
 */
function hookGlobalSymbolAccess(sym, func) {
  // In MODULARIZE mode the generated code runs inside a function scope and not
  // the global scope, and JavaScript does not provide access to function scopes
  // so we cannot dynamically modify the scrope using `defineProperty` in this
  // case.
  //
  // In this mode we simply ignore requests for `hookGlobalSymbolAccess`. Since
  // this is a debug-only feature, skipping it is not major issue.
}

function missingGlobal(sym, msg) {
  hookGlobalSymbolAccess(sym, () => {
    warnOnce(`\`${sym}\` is not longer defined by emscripten. ${msg}`);
  });
}

missingGlobal('buffer', 'Please use HEAP8.buffer or wasmMemory.buffer');
missingGlobal('asm', 'Please use wasmExports instead');

function missingLibrarySymbol(sym) {
  hookGlobalSymbolAccess(sym, () => {
    // Can't `abort()` here because it would break code that does runtime
    // checks.  e.g. `if (typeof SDL === 'undefined')`.
    var msg = `\`${sym}\` is a library symbol and not included by default; add it to your library.js __deps or to DEFAULT_LIBRARY_FUNCS_TO_INCLUDE on the command line`;
    // DEFAULT_LIBRARY_FUNCS_TO_INCLUDE requires the name as it appears in
    // library.js, which means $name for a JS name with no prefix, or name
    // for a JS name like _name.
    var librarySymbol = sym;
    if (!librarySymbol.startsWith('_')) {
      librarySymbol = '$' + sym;
    }
    msg += ` (e.g. -sDEFAULT_LIBRARY_FUNCS_TO_INCLUDE='${librarySymbol}')`;
    if (isExportedByForceFilesystem(sym)) {
      msg += '. Alternatively, forcing filesystem support (-sFORCE_FILESYSTEM) can export this for you';
    }
    warnOnce(msg);
  });

  // Any symbol that is not included from the JS library is also (by definition)
  // not exported on the Module object.
  unexportedRuntimeSymbol(sym);
}

function unexportedRuntimeSymbol(sym) {
  if (!Object.getOwnPropertyDescriptor(Module, sym)) {
    Object.defineProperty(Module, sym, {
      configurable: true,
      get() {
        var msg = `'${sym}' was not exported. add it to EXPORTED_RUNTIME_METHODS (see the Emscripten FAQ)`;
        if (isExportedByForceFilesystem(sym)) {
          msg += '. Alternatively, forcing filesystem support (-sFORCE_FILESYSTEM) can export this for you';
        }
        abort(msg);
      }
    });
  }
}

// end include: runtime_debug.js
// include: memoryprofiler.js
// end include: memoryprofiler.js


function updateMemoryViews() {
  var b = wasmMemory.buffer;
  HEAP8 = new Int8Array(b);
  HEAP16 = new Int16Array(b);
  HEAPU8 = new Uint8Array(b);
  HEAPU16 = new Uint16Array(b);
  HEAP32 = new Int32Array(b);
  HEAPU32 = new Uint32Array(b);
  HEAPF32 = new Float32Array(b);
  HEAPF64 = new Float64Array(b);
  HEAP64 = new BigInt64Array(b);
  HEAPU64 = new BigUint64Array(b);
}

// end include: runtime_shared.js
assert(typeof Int32Array != 'undefined' && typeof Float64Array !== 'undefined' && Int32Array.prototype.subarray != undefined && Int32Array.prototype.set != undefined,
       'JS engine does not provide full typed array support');

function preRun() {
  if (Module['preRun']) {
    if (typeof Module['preRun'] == 'function') Module['preRun'] = [Module['preRun']];
    while (Module['preRun'].length) {
      addOnPreRun(Module['preRun'].shift());
    }
  }
  consumedModuleProp('preRun');
  // Begin ATPRERUNS hooks
  callRuntimeCallbacks(onPreRuns);
  // End ATPRERUNS hooks
}

function initRuntime() {
  assert(!runtimeInitialized);
  runtimeInitialized = true;

  checkStackCookie();

  // Begin ATINITS hooks
  if (!Module['noFSInit'] && !FS.initialized) FS.init();
TTY.init();
  // End ATINITS hooks

  wasmExports['__wasm_call_ctors']();

  // Begin ATPOSTCTORS hooks
  FS.ignorePermissions = false;
  // End ATPOSTCTORS hooks
}

function postRun() {
  checkStackCookie();
   // PThreads reuse the runtime from the main thread.

  if (Module['postRun']) {
    if (typeof Module['postRun'] == 'function') Module['postRun'] = [Module['postRun']];
    while (Module['postRun'].length) {
      addOnPostRun(Module['postRun'].shift());
    }
  }
  consumedModuleProp('postRun');

  // Begin ATPOSTRUNS hooks
  callRuntimeCallbacks(onPostRuns);
  // End ATPOSTRUNS hooks
}

// A counter of dependencies for calling run(). If we need to
// do asynchronous work before running, increment this and
// decrement it. Incrementing must happen in a place like
// Module.preRun (used by emcc to add file preloading).
// Note that you can add dependencies in preRun, even though
// it happens right before run - run will be postponed until
// the dependencies are met.
var runDependencies = 0;
var dependenciesFulfilled = null; // overridden to take different actions when all run dependencies are fulfilled
var runDependencyTracking = {};
var runDependencyWatcher = null;

function getUniqueRunDependency(id) {
  var orig = id;
  while (1) {
    if (!runDependencyTracking[id]) return id;
    id = orig + Math.random();
  }
}

function addRunDependency(id) {
  runDependencies++;

  Module['monitorRunDependencies']?.(runDependencies);

  if (id) {
    assert(!runDependencyTracking[id]);
    runDependencyTracking[id] = 1;
    if (runDependencyWatcher === null && typeof setInterval != 'undefined') {
      // Check for missing dependencies every few seconds
      runDependencyWatcher = setInterval(() => {
        if (ABORT) {
          clearInterval(runDependencyWatcher);
          runDependencyWatcher = null;
          return;
        }
        var shown = false;
        for (var dep in runDependencyTracking) {
          if (!shown) {
            shown = true;
            err('still waiting on run dependencies:');
          }
          err(`dependency: ${dep}`);
        }
        if (shown) {
          err('(end of list)');
        }
      }, 10000);
    }
  } else {
    err('warning: run dependency added without ID');
  }
}

function removeRunDependency(id) {
  runDependencies--;

  Module['monitorRunDependencies']?.(runDependencies);

  if (id) {
    assert(runDependencyTracking[id]);
    delete runDependencyTracking[id];
  } else {
    err('warning: run dependency removed without ID');
  }
  if (runDependencies == 0) {
    if (runDependencyWatcher !== null) {
      clearInterval(runDependencyWatcher);
      runDependencyWatcher = null;
    }
    if (dependenciesFulfilled) {
      var callback = dependenciesFulfilled;
      dependenciesFulfilled = null;
      callback(); // can add another dependenciesFulfilled
    }
  }
}

/** @param {string|number=} what */
function abort(what) {
  Module['onAbort']?.(what);

  what = 'Aborted(' + what + ')';
  // TODO(sbc): Should we remove printing and leave it up to whoever
  // catches the exception?
  err(what);

  ABORT = true;

  // Use a wasm runtime error, because a JS error might be seen as a foreign
  // exception, which means we'd run destructors on it. We need the error to
  // simply make the program stop.
  // FIXME This approach does not work in Wasm EH because it currently does not assume
  // all RuntimeErrors are from traps; it decides whether a RuntimeError is from
  // a trap or not based on a hidden field within the object. So at the moment
  // we don't have a way of throwing a wasm trap from JS. TODO Make a JS API that
  // allows this in the wasm spec.

  // Suppress closure compiler warning here. Closure compiler's builtin extern
  // definition for WebAssembly.RuntimeError claims it takes no arguments even
  // though it can.
  // TODO(https://github.com/google/closure-compiler/pull/3913): Remove if/when upstream closure gets fixed.
  /** @suppress {checkTypes} */
  var e = new WebAssembly.RuntimeError(what);

  readyPromiseReject(e);
  // Throw the error whether or not MODULARIZE is set because abort is used
  // in code paths apart from instantiation where an exception is expected
  // to be thrown when abort is called.
  throw e;
}

function createExportWrapper(name, nargs) {
  return (...args) => {
    assert(runtimeInitialized, `native function \`${name}\` called before runtime initialization`);
    var f = wasmExports[name];
    assert(f, `exported native function \`${name}\` not found`);
    // Only assert for too many arguments. Too few can be valid since the missing arguments will be zero filled.
    assert(args.length <= nargs, `native function \`${name}\` called with ${args.length} args but expects ${nargs}`);
    return f(...args);
  };
}

var wasmBinaryFile;

function findWasmBinary() {
  return base64Decode('AGFzbQEAAAABkgQ+YAJ/fwF8YAF/AX9gA39/fwF/YAN/fn8BfmAGf3x/f39/AX9gAn9/AGACf38Bf2AFf39/f38Bf2AEf39/fwF/YAR/fn9/AX9gAABgAAF8YAF8AXxgDH9/f39/f39/f39/fwF8YA98f39/f39/f39/f39/f38BfGAWf39/f39/f39/f39/f39/f39/f39/fwF8YAl/f39/f39/f38Bf2AGf39/f39/AXxgEH9/f39/f39/f39/f39/f38BfGAHf39/f39/fwF8YCR8f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f39/f38BfGAHf39/f39/fwF/YAd/f39/fH98AGABfwBgAAF/YAN/f38BfGAEf39/fwBgA39/fwBgBH9/fH8AYAN/f3wBfGACf3wBfGAHf39/f39/fwBgCn9/f39/f39/f38AYAV/f398fwF8YAZ/f39/f38AYAF/AXxgEnx/f39/f39/f39/f39/f39/fwF8YAN/fn8Bf2ABfwF+YAF8AX9gAnx8AXxgAX4Bf2ACfn8BfGADfHx/AXxgA3x+fgF8YAF8AGACf34AYAJ8fwF8YAV/fn5+fgBgBH9+fn8AYAJ+fgF/YAN/fn4AYAJ/fwF+YAR/f39+AX5gA35/fwF/YAJ+fwF/YAV/f39/fwBgAXwBfmAEfn5+fgF/YAJ/fABgAn99AGACfn4BfAK8AgwDZW52CWludm9rZV9paQAGA2VudgxpbnZva2VfaWlpaWkABwNlbnYQX19zeXNjYWxsX29wZW5hdAAIA2VudhFfX3N5c2NhbGxfZmNudGw2NAACA2Vudg9fX3N5c2NhbGxfaW9jdGwAAhZ3YXNpX3NuYXBzaG90X3ByZXZpZXcxCGZkX3dyaXRlAAgWd2FzaV9zbmFwc2hvdF9wcmV2aWV3MQdmZF9yZWFkAAgWd2FzaV9zbmFwc2hvdF9wcmV2aWV3MQhmZF9jbG9zZQABFndhc2lfc25hcHNob3RfcHJldmlldzEHZmRfc2VlawAJA2VudglfYWJvcnRfanMACgNlbnYWZW1zY3JpcHRlbl9yZXNpemVfaGVhcAABA2VudhlfZW1zY3JpcHRlbl90aHJvd19sb25nam1wAAoD5wHlAQoLDA0ODxARERITBxMUFQUAFgAAAQEBARcXFxgBBgABBgYGBgYCAhkZAgIGGhsbHB0eBh8GIBwdBgYbGwYIIQEGHQYiBhoFGiMaGgUBAQEBGgEkARcXAQEYAQIDAgIBAQYGAgIBCCUlAiYmAQEjDAwMJwMXFxgKAR4MIyMMKCcpKQwqKywtFwgGBgYGBgECAS4BLzAxMjAzGgEiHzQaADUBAgEBAQIGLwIHFRsBGjY3NzgCBAU5CAIBGBgYCgIGCgECFwYYATAxOjowBRsGBRcYOzwFBRgYMTAwChgYGDA9FwEYBgEEBQFwAQ0NBQcBAYICgIACBhcEfwFBgIAEC38BQQALfwFBAAt/AUEACwfyCkAGbWVtb3J5AgARX193YXNtX2NhbGxfY3RvcnMADAdtcW1xYV9SAA0abXFtcWFfaWRlYWxfZW50cm9weV9iaW5hcnkADhZtcW1xYV9yZWZlcmVuY2VfZW5lcmd5AA8ZbXFtcWFfaWRlYWxfbWl4aW5nX2VuZXJneQAQBGZyZWUAzgETbXFtcWFfZXhjZXNzX2VuZXJneQAREm1xbXFhX2Nvb3JkaW5hdGlvbgAVEW1xbXFhX2VxdWlsaWJyYXRlABkGbWFsbG9jAMwBGV9faW5kaXJlY3RfZnVuY3Rpb25fdGFibGUBABRtcW1xYV9kYl9yZWFkX3N0cmluZwAgEm1xbXFhX2RiX3JlYWRfZmlsZQAjDW1xbXFhX2RiX2ZyZWUAJA5tcW1xYV9kYl9lcnJvcgAnFW1xbXFhX2RiX251bV9lbGVtZW50cwAoEG1xbXFhX2RiX2VsZW1lbnQAKRVtcW1xYV9kYl9lbGVtZW50X21hc3MAKhNtcW1xYV9kYl9udW1fcGhhc2VzACsUbXFtcWFfZGJfcGhhc2VfaW5kZXgALBNtcW1xYV9kYl9waGFzZV9uYW1lAC0WbXFtcWFfZGJfcGhhc2VfaXNfc3VicQAuFG1xbXFhX3BoX251bV9jYXRpb25zAC8TbXFtcWFfcGhfbnVtX2FuaW9ucwAwD21xbXFhX3BoX2NhdGlvbgAxDm1xbXFhX3BoX2FuaW9uADIWbXFtcWFfcGhfY2F0aW9uX2NoYXJnZQAzFW1xbXFhX3BoX2FuaW9uX2NoYXJnZQA0FW1xbXFhX3BoX2NhdGlvbl9ncm91cAA1FG1xbXFhX3BoX2FuaW9uX2dyb3VwADYSbXFtcWFfcGhfbnVtX3BhaXJzADcVbXFtcWFfcGhfcGFpcl9pbmRpY2VzADgUbXFtcWFfcGhfcGFpcl9zdG9pY2gAORJtcW1xYV9waF9wYWlyX3pldGEAOhNtcW1xYV9waF9wYWlyX2dpYmJzADsRbXFtcWFfcGhfbnVtX21xbXoAPg1tcW1xYV9waF9tcW16AD8RbXFtcWFfcGhfbnVtX21xbXgAQA1tcW1xYV9waF9tcW14AEEPbXFtcWFfcGhfbXFteF9MAEITbXFtcWFfZGJfcGhhc2Vfa2luZABEFW1xbXFhX3BoX2NlZl9udW1fc3VibABFFm1xbXFhX3BoX2NlZl9zdWJsX25jb24ARhdtcW1xYV9waF9jZWZfc2l0ZV9yYXRpbwBHHW1xbXFhX3BoX2NlZl9udW1fY29uc3RpdHVlbnRzAEgYbXFtcWFfcGhfY2VmX2NvbnN0aXR1ZW50AEkSbXFtcWFfcGhfY2VmX2dpYmJzAEoPbXFtcWFfY2VmX2dpYmJzAF4TbXFtcWFfZGJfbnVtX3N0b2ljaABLFG1xbXFhX2RiX3N0b2ljaF9uYW1lAEwVbXFtcWFfZGJfc3RvaWNoX2dpYmJzAE0VbXFtcWFfbnVtX3F1YWRydXBsZXRzAE4bbXFtcWFfZW51bWVyYXRlX3F1YWRydXBsZXRzAE8GZmZsdXNoAGMIc3RyZXJyb3IA8AEYZW1zY3JpcHRlbl9zdGFja19nZXRfZW5kAOkBGWVtc2NyaXB0ZW5fc3RhY2tfZ2V0X2Jhc2UA6AEIc2V0VGhyZXcA1wEVZW1zY3JpcHRlbl9zdGFja19pbml0AOYBGWVtc2NyaXB0ZW5fc3RhY2tfZ2V0X2ZyZWUA5wEZX2Vtc2NyaXB0ZW5fc3RhY2tfcmVzdG9yZQDsARdfZW1zY3JpcHRlbl9zdGFja19hbGxvYwDtARxlbXNjcmlwdGVuX3N0YWNrX2dldF9jdXJyZW50AO4BCRcBAEEBCwwcHq8BIpMBZ2hpa78BwAHDAQqUtAXlAQgAEOYBEMgBCwwARBsv3SQGoSBADwvFAQIBfwZ8I4CAgIAAQRBrIQEgASSAgICAACABIAA5AwACQAJAAkAgASsDAEEAt2VBAXENACABKwMARAAAAAAAAPA/ZkEBcUUNAQsgAUEAtzkDCAwBCyABKwMAIQIgASsDABD8gICAACEDIAErAwAhBEQA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AgwoAhwgAigCDCgCICACKAIIIAIoAgwoAiQgAigCDCgCKCACKAIMKAIsIAIoAgwoAjAgAigCDCgCNCACKAIMKAI4EJCAgIAAoCACKAIMKAIIIAIoAgwoAgwgAigCDCgCECACKAIMKAIUIAIoAgwoAhggAigCDCgCHCACKAIMKAIgIAIoAgggAigCDCgCJCACKAIMKAIoIAIoAgwoAiwgAigCDCgCMCACKAIMKAJUIAIoAgwoAlggAigCDCgCXCACKAIMKAJgIAIoAgwoAmQgAigCDCgCaCACKAIMKAJsIAIoAgwoAnAgAigCDCgCdCACKAIMKAJ4EJGAgIAAoCEDIAJBEGokgICAgAAgAw8L6gEBCH8jgICAgABBEGshASABJICAgIAAIAEgADYCCAJAAkAgASgCCEEAR0EBcQ0AQdDyhIAAIQJBtICEgAAhA0EAIQQgAkGAAiADIAQQk4GAgAAaIAFBADYCDAwBCyABIAEoAggQmYGAgABBAWoQzIGAgAA2AgQCQCABKAIEQQBHQQFxDQBB0PKEgAAhBUGJgISAACEGQQAhByAFQYACIAYgBxCTgYCAABogAUEANgIMDAELIAEoAgQgASgCCBCYgYCAABogASABKAIEEKGAgIAANgIMCyABKAIMIQggAUEQaiSAgICAACAIDwvtCAE+fyOAgICAAEEQayEBIAEhAiABJICAgIAAIAEhA0FwIQQgAyAEaiEFIAUhASABJICAgIAAIAQgAWohBiAGIQEgASSAgICAACABQZB8aiEHIAchASABJICAgIAAIAQgAWohCCAIIQEgASSAgICAACAFIAA2AgAgBiAFKAIANgIAA38gBigCAC0AACEJQQAhCgJAAkACQAJAAkACQAJAAkACQAJAAkAgCUH/AXEgCkH/AXFHQQFxRQ0AIAYoAgAtAABB/wFxIQtBACEMQQAgDDYClPqEgABBg4CAgAAgCxCAgICAACENQQAoApT6hIAAIQ5BACEPQQAgDzYClPqEgAAgDkEARyEQQQAoApj6hIAAIREgECARQQBHcUEBcQ0BDAILQfADIRJBACETAkAgEkUNACAHIBMgEvwLAAsgByAFKAIANgIAIAdBATYCCCAHQQA6APABIAcgBSgCADYCBANAIAcoAgQtAAAhFEEYIRUgFCAVdCAVdSEWQQAhFwJAIBZFDQAgBygCBC0AACEYQRghGSAYIBl0IBl1QQpHIRcLAkAgF0EBcUUNACAHIAcoAgRBAWo2AgQMAQsLIAcoAgQtAAAhGkEYIRsCQCAaIBt0IBt1QQpGQQFxRQ0AIAcgBygCBEEBajYCBCAHIAcoAghBAWo2AggLIAhBADYCACAHQdQAakEBIAJBDGoQ2IGAgABBACEcDAQLIA4gAkEMahDZgYCAACEdIA4hHiARIR8gHUUNBAwBC0F/ISAMAQsgERDbgYCAACAdISALICAhIRDcgYCAACEiICFBAUYhIyAiIRwgI0UNBQsDQAJAAkACQAJAAkACQAJAAkACQCAcDQBBACEkQQAgJDYClPqEgABBhICAgAAgBxCAgICAACElQQAoApT6hIAAISZBACEnQQAgJzYClPqEgAAgJkEARyEoQQAoApj6hIAAISkgKCApQQBHcUEBcQ0BDAILQdDyhIAAISogB0HwAWohK0EAISxBACAsNgKU+oSAACACICs2AgBB/oKEgAAhLUGFgICAACAqQYACIC0gAhCBgICAABpBACgClPqEgAAhLkEAIS9BACAvNgKU+oSAACAuQQBHITBBACgCmPqEgAAhMSAwIDFBAEdxQQFxDQMMBAsgJiACQQxqENmBgIAAITIgJiEeICkhHyAyRQ0IDAELQX8hMwwFCyApENuBgIAAIDIhMwwECyAuIAJBDGoQ2YGAgAAhNCAuIR4gMSEfIDRFDQUMAQtBfyE1DAELIDEQ24GAgAAgNCE1CyA1ITYQ3IGAgAAhNyA2QQFGITggNyEcIDgNAQwDCyAzITkQ3IGAgAAhOiA5QQFGITsgOiEcIDsNAAwDCwsgHyE8IB4gPBDagYCAAAALIAhBADYCAAwBCyAIICU2AgBBACE9QQAgPToA0PKEgAALIAUoAgAQzoGAgAAgCCgCACE+IAJBEGokgICAgAAgPg8LIAYoAgAgDToAACAGIAYoAgBBAWo2AgAMAAsL+gYBE38jgICAgABB8AhrIQEgASSAgICAACABIAA2AuwIIAEgASgC7AhBpAEQ0ICAgAA2AugIIAFBADYCXCABKALsCCABKALoCCABQeAAaiABQdwAahDRgICAACABKALsCCECAkACQCABKAJcRQ0AIAEoAlwhAwwBC0EBIQMLIAIgA0GQAWwQ0ICAgAAhBCABKALoCCAENgKYASABKALoCEEANgKUASABQQA2AlgCQANAIAEoAlggASgCXEhBAXFFDQEgASgCWCEFAkACQCABQeAAaiAFQQJ0aigCAA0ADAELIAEgASgC6AgoApgBIAEoAugIKAKUAUGQAWxqNgJUIAEoAlQhBkGQASEHQQAhCAJAIAdFDQAgBiAIIAf8CwALIAEoAuwIIAEoAlQQ0oCAgAAgASgC7AggAUEQahDSgICAAAJAAkACQCABQRBqQY2IhIAAEJaBgIAARQ0AIAFBEGpBoYiEgAAQloGAgAANAQsgASgC7AggASgC6AggASgCVCABQRBqENOAgIAADAELAkACQCABQRBqQZyIhIAAQQQQmoGAgAANAAJAIAFBEGpBloiEgAAQloGAgAANACABKALsCBDUgICAABogASgC7AgQ1ICAgAAaCyABKALsCCEJIAEoAugIIQogASgCVCELIAEoAlghDCAJIAogCyABQeAAaiAMQQJ0aigCABDVgICAAAwBCyABKALsCEHwAWohDSABIAFBEGo2AgBBtoiEgAAhDiANQYACIA4gARCTgYCAABogASgC7AhB1ABqQQEQ2oGAgAAACwsgASgC6AghDyAPIA8oApQBQQFqNgKUAQsgASABKAJYQQFqNgJYDAALCyABKALsCCEQAkACQCABKALoCCgCnAFFDQAgASgC6AgoApwBIREMAQtBASERCyAQIBFBiAFsENCAgIAAIRIgASgC6AggEjYCoAEgAUEANgIMAkADQCABKAIMIAEoAugIKAKcAUhBAXFFDQEgASgC7AggASgC6AgoAqABIAEoAgxBiAFsaiABKALoCCgCACABKALoCCgCDBDWgICAAAJAIAEoAugIKAKgASABKAIMQYgBbGooAkxFDQAgASgC7AgQ1ICAgAAaIAEoAuwIENSAgIAAGgsgASABKAIMQQFqNgIMDAALCyABKALoCCETIAFB8AhqJICAgIAAIBMPC5QEARF/I4CAgIAAQSBrIQEgASSAgICAACABIAA2AhggASABKAIYQYaIhIAAEO2AgIAANgIUAkACQCABKAIUQQBHQQFxDQBB0PKEgAAhAgJAAkAgASgCGEEAR0EBcUUNACABKAIYIQMMAQtBr4iEgAAhAwsgASADNgIAQeaChIAAIQQgAkGAAiAEIAEQk4GAgAAaIAFBADYCHAwBCwJAIAEoAhRBAEECEPSAgIAARQ0AIAEoAhQQ4oCAgAAaQdDyhIAAIQVB+oeEgAAhBkEAIQcgBUGAAiAGIAcQk4GAgAAaIAFBADYCHAwBCyABIAEoAhQQ94CAgAA2AhACQCABKAIQQQBIQQFxRQ0AIAEoAhQQ4oCAgAAaQdDyhIAAIQhB7oeEgAAhCUEAIQogCEGAAiAJIAoQk4GAgAAaIAFBADYCHAwBCyABKAIUEJKBgIAAIAEgASgCEEEBahDMgYCAADYCDAJAIAEoAgxBAEdBAXENACABKAIUEOKAgIAAGkHQ8oSAACELQYmAhIAAIQxBACENIAtBgAIgDCANEJOBgIAAGiABQQA2AhwMAQsgASgCDCEOIAEoAhAhDyABKAIUIRAgASAOQQEgDyAQEPGAgIAANgIIIAEoAhQQ4oCAgAAaIAEoAgwgASgCCGpBADoAACABIAEoAgwQoYCAgAA2AhwLIAEoAhwhESABQSBqJICAgIAAIBEPCzUBAX8jgICAgABBEGshASABJICAgIAAIAEgADYCDCABKAIMEKWAgIAAIAFBEGokgICAgAAPC/QGAQF/I4CAgIAAQTBrIQEgASSAgICAACABIAA2AiwCQAJAIAEoAixBAEdBAXENAAwBCyABQQA2AigCQANAIAEoAiggASgCLCgClAFIQQFxRQ0BIAEgASgCLCgCmAEgASgCKEGQAWxqNgIkIAFBADYCIAJAA0AgASgCICABKAIkKAJYSEEBcUUNASABKAIkKAJ4IAEoAiBBiAFsahCmgICAACABIAEoAiBBAWo2AiAMAAsLIAEoAiQoAngQzoGAgAAgASgCJCgCYBDOgYCAACABKAIkKAJkEM6BgIAAIAEoAiQoAmgQzoGAgAAgASgCJCgCbBDOgYCAACABKAIkKAJwEM6BgIAAIAEoAiQoAnQQzoGAgAAgASgCJCgCfBDOgYCAACABQQA2AhwCQANAIAEoAhwgASgCJCgCgAFIQQFxRQ0BIAEoAiQoAoQBIAEoAhxBLGxqKAIoEM6BgIAAIAEgASgCHEEBajYCHAwACwsgASgCJCgChAEQzoGAgAACQCABKAIkKAKIAUEAR0EBcUUNACABIAEoAiQoAogBNgIYIAFBADYCFAJAA0AgASgCFCABKAIYKAIcSEEBcUUNASABKAIYKAIgIAEoAhRBiAFsahCmgICAACABIAEoAhRBAWo2AhQMAAsLIAEoAhgoAiAQzoGAgAAgASgCGCgCBBDOgYCAACABKAIYKAIIEM6BgIAAIAEoAhgoAgwQzoGAgAAgASgCGCgCFBDOgYCAACABKAIYKAIYEM6BgIAAIAEoAhgoAiQQzoGAgAAgAUEANgIQAkADQCABKAIQIAEoAhgoAihIQQFxRQ0BIAEoAhgoAiwgASgCEEEYbGooAhAQzoGAgAAgASgCGCgCLCABKAIQQRhsaigCFBDOgYCAACABIAEoAhBBAWo2AhAMAAsLIAEoAhgoAiwQzoGAgAAgASgCGBDOgYCAAAsgASABKAIoQQFqNgIoDAALCyABKAIsKAKYARDOgYCAACABQQA2AgwCQANAIAEoAgwgASgCLCgCnAFIQQFxRQ0BIAEoAiwoAqABIAEoAgxBiAFsahCmgICAACABIAEoAgxBAWo2AgwMAAsLIAEoAiwoAqABEM6BgIAAIAEoAiwoAgQQzoGAgAAgASgCLCgCCBDOgYCAACABKAIsEM6BgIAACyABQTBqJICAgIAADwuuAQEBfyOAgICAAEEQayEBIAEkgICAgAAgASAANgIMIAFBADYCCAJAA0AgASgCCCABKAIMKAJESEEBcUUNASABKAIMKAJIIAEoAghBmAFsaigCjAEQzoGAgAAgASgCDCgCSCABKAIIQZgBbGooApABEM6BgIAAIAEgASgCCEEBajYCCAwACwsgASgCDCgCSBDOgYCAACABKAIMKAJAEM6BgIAAIAFBEGokgICAgAAPCwkAQdDyhIAADwsfAQF/I4CAgIAAQRBrIQEgASAANgIMIAEoAgwoAgAPCy8BAX8jgICAgABBEGshAiACIAA2AgwgAiABNgIIIAIoAgwoAgQgAigCCEEGdGoPCzIBAX8jgICAgABBEGshAiACIAA2AgwgAiABNgIIIAIoAgwoAgggAigCCEEDdGorAwAPCyABAX8jgICAgABBEGshASABIAA2AgwgASgCDCgClAEPC64BAQJ/I4CAgIAAQSBrIQIgAiSAgICAACACIAA2AhggAiABNgIUIAIgAigCGDYCECACQQA2AgwCQAJAA0AgAigCDCACKAIQKAKUAUhBAXFFDQECQCACKAIQKAKYASACKAIMQZABbGogAigCFBCWgYCAAA0AIAIgAigCDDYCHAwDCyACIAIoAgxBAWo2AgwMAAsLIAJBfzYCHAsgAigCHCEDIAJBIGokgICAgAAgAw8LMQEBfyOAgICAAEEQayECIAIgADYCDCACIAE2AgggAigCDCgCmAEgAigCCEGQAWxqDws0AQF/I4CAgIAAQRBrIQIgAiAANgIMIAIgATYCCCACKAIMKAKYASACKAIIQZABbGooAkQPCzQBAX8jgICAgABBEGshAiACIAA2AgwgAiABNgIIIAIoAgwoApgBIAIoAghBkAFsaigCUA8LNAEBfyOAgICAAEEQayECIAIgADYCDCACIAE2AgggAigCDCgCmAEgAigCCEGQAWxqKAJUDwtEAQF/I4CAgIAAQRBrIQMgAyAANgIMIAMgATYCCCADIAI2AgQgAygCDCgCmAEgAygCCEGQAWxqKAJgIAMoAgRBBnRqDwtEAQF/I4CAgIAAQRBrIQMgAyAANgIMIAMgATYCCCADIAI2AgQgAygCDCgCmAEgAygCCEGQAWxqKAJkIAMoAgRBBnRqDwtHAQF/I4CAgIAAQRBrIQMgAyAANgIMIAMgATYCCCADIAI2AgQgAygCDCgCmAEgAygCCEGQAWxqKAJoIAMoAgRBA3RqKwMADwtHAQF/I4CAgIAAQRBrIQMgAyAANgIMIAMgATYCCCADIAI2AgQgAygCDCgCmAEgAygCCEGQAWxqKAJsIAMoAgRBA3RqKwMADwtHAQF/I4CAgIAAQRBrIQMgAyAANgIMIAMgATYCCCADIAI2AgQgAygCDCgCmAEgAygCCEGQAWxqKAJwIAMoAgRBAnRqKAIADwtHAQF/I4CAgIAAQRBrIQMgAyAANgIMIAMgATYCCCADIAI2AgQgAygCDCgCmAEgAygCCEGQAWxqKAJ0IAMoAgRBAnRqKAIADws0AQF/I4CAgIAAQRBrIQIgAiAANgIMIAIgATYCCCACKAIMKAKYASACKAIIQZABbGooAlgPC8oBAQN/I4CAgIAAQSBrIQQgBCAANgIcIAQgATYCGCAEIAI2AhQgBCADNgIQIAQgBCgCHCgCmAEgBCgCGEGQAWxqNgIMIARBADYCCAJAA0AgBCgCCCAEKAIMKAJYSEEBcUUNASAEKAIMKAJ4IAQoAghBiAFsaigCgAEhBSAEKAIUIAQoAghBAnRqIAU2AgAgBCgCDCgCeCAEKAIIQYgBbGooAoQBIQYgBCgCECAEKAIIQQJ0aiAGNgIAIAQgBCgCCEEBajYCCAwACwsPC5kBAgF/AXwjgICAgABBIGshAyADIAA2AhwgAyABNgIYIAMgAjYCFCADIAMoAhwoApgBIAMoAhhBkAFsajYCECADQQA2AgwCQANAIAMoAgwgAygCECgCWEhBAXFFDQEgAygCECgCeCADKAIMQYgBbGorA1AhBCADKAIUIAMoAgxBA3RqIAQ5AwAgAyADKAIMQQFqNgIMDAALCw8LmQECAX8BfCOAgICAAEEgayEDIAMgADYCHCADIAE2AhggAyACNgIUIAMgAygCHCgCmAEgAygCGEGQAWxqNgIQIANBADYCDAJAA0AgAygCDCADKAIQKAJYSEEBcUUNASADKAIQKAJ4IAMoAgxBiAFsaisDeCEEIAMoAhQgAygCDEEDdGogBDkDACADIAMoAgxBAWo2AgwMAAsLDwvKAQIBfwF8I4CAgIAAQSBrIQQgBCSAgICAACAEIAA2AhwgBCABNgIYIAQgAjkDECAEIAM2AgwgBCAEKAIcNgIIIAQgBCgCCCgCmAEgBCgCGEGQAWxqNgIEIARBADYCAAJAA0AgBCgCACAEKAIEKAJYSEEBcUUNASAEKAIIIAQoAgQoAnggBCgCAEGIAWxqIAQrAxAQvICAgAAhBSAEKAIMIAQoAgBBA3RqIAU5AwAgBCAEKAIAQQFqNgIADAALCyAEQSBqJICAgIAADwufBAIBfwR8I4CAgIAAQcAAayEDIAMkgICAgAAgAyAANgI0IAMgATYCMCADIAI5AyggA0EANgIkIANBADYCIAJAA0AgAygCICADKAIwKAJESEEBcUUNAQJAIAMrAyggAygCMCgCSCADKAIgQZgBbGorAwBjQQFxRQ0AIAMgAygCMCgCSCADKAIgQZgBbGo2AiQMAgsgAyADKAIgQQFqNgIgDAALCwJAAkAgAygCJEEAR0EBcQ0AIANBALc5AzgMAQsgA0EAtzkDGCADQQA2AhQCQANAIAMoAhQgAygCNCgCDEhBAXFFDQEgAygCJEEIaiADKAIUQQN0aisDACEEIAMoAjRBEGogAygCFEECdGooAgAgAysDKBC9gICAACEFIAMgAysDGCAEIAWioDkDGCADIAMoAhRBAWo2AhQMAAsLIANBADYCEAJAA0AgAygCECADKAIkKAKIAUhBAXFFDQEgAyADKAIkKAKQASADKAIQQQN0aisDADkDCAJAAkAgAysDCEQAAAAAAMBYQGFBAXFFDQAgAygCJCgCjAEgAygCEEEDdGorAwAgAysDKBD8gICAAKIhBgwBCyADKAIkKAKMASADKAIQQQN0aisDACADKwMoIAMrAwgQiYGAgACiIQYLIAMgBiADKwMYoDkDGCADIAMoAhBBAWo2AhAMAAsLIAMgAysDGDkDOAsgAysDOCEHIANBwABqJICAgIAAIAcPC5YCAgJ/AnwjgICAgABBIGshAiACJICAgIAAIAIgADYCFCACIAE5AwggAigCFCEDIANBCEsaAkACQAJAAkACQAJAAkACQAJAAkACQCADDgkAAQIDBAUGBwgJCyACQQC3OQMYDAkLIAJEAAAAAAAA8D85AxgMCAsgAiACKwMIOQMYDAcLIAIgAisDCCACKwMIEPyAgIAAojkDGAwGCyACIAIrAwggAisDCKI5AxgMBQsgAiACKwMIIAIrAwiiIAIrAwiiOQMYDAQLIAIrAwghBCACRAAAAAAAAPA/IASjOQMYDAMLIAJBALc5AxgMAgsgAkEAtzkDGAwBCyACQQC3OQMYCyACKwMYIQUgAkEgaiSAgICAACAFDws0AQF/I4CAgIAAQRBrIQIgAiAANgIMIAIgATYCCCACKAIMKAKYASACKAIIQZABbGooAlwPC5cDAgV/AXwjgICAgABBMGshByAHIAA2AiwgByABNgIoIAcgAjYCJCAHIAM2AiAgByAENgIcIAcgBTYCGCAHIAY2AhQgByAHKAIsKAKYASAHKAIoQZABbGo2AhAgB0EANgIMAkADQCAHKAIMIAcoAhAoAlxIQQFxRQ0BIAcoAhAoAnwgBygCDEEwbGooAgAhCCAHKAIkIAcoAgxBAnRqIAg2AgAgBygCECgCfCAHKAIMQTBsaigCBCEJIAcoAiAgBygCDEECdGogCTYCACAHKAIQKAJ8IAcoAgxBMGxqKAIIIQogBygCHCAHKAIMQQJ0aiAKNgIAIAcoAhAoAnwgBygCDEEwbGooAgwhCyAHKAIYIAcoAgxBAnRqIAs2AgAgB0EANgIIAkADQCAHKAIIQQRIQQFxRQ0BIAcoAhAoAnwgBygCDEEwbGpBEGogBygCCEEDdGorAwAhDCAHKAIUIAcoAgxBAnQgBygCCGpBA3RqIAw5AwAgByAHKAIIQQFqNgIIDAALCyAHIAcoAgxBAWo2AgwMAAsLDws1AQF/I4CAgIAAQRBrIQIgAiAANgIMIAIgATYCCCACKAIMKAKYASACKAIIQZABbGooAoABDwvNBAEVfyOAgICAAEHAAGshCiAKIAA2AjwgCiABNgI4IAogAjYCNCAKIAM2AjAgCiAENgIsIAogBTYCKCAKIAY2AiQgCiAHNgIgIAogCDYCHCAKIAk2AhggCiAKKAI8KAKYASAKKAI4QZABbGo2AhQgCkEANgIQAkADQCAKKAIQIAooAhQoAoABSEEBcUUNASAKIAooAhQoAoQBIAooAhBBLGxqNgIMIAooAgwoAgQhCyAKKAI0IAooAhBBAnRqIAs2AgAgCigCDC0AACEMQRghDQJAAkAgDCANdCANdUHRAEZBAXFFDQBBACEODAELIAooAgwtAAAhD0EYIRACQAJAIA8gEHQgEHVBxwBGQQFxRQ0AQQEhEQwBCyAKKAIMLQAAIRJBGCETAkACQCASIBN0IBN1QcIARkEBcUUNAEECIRQMAQsgCigCDC0AACEVQRghFiAVIBZ0IBZ1QdIARiEXQQNBfyAXQQFxGyEUCyAUIRELIBEhDgsgDiEYIAooAjAgCigCEEECdGogGDYCACAKKAIMKAIIIRkgCigCLCAKKAIQQQJ0aiAZNgIAIAooAgwoAgwhGiAKKAIoIAooAhBBAnRqIBo2AgAgCigCDCgCECEbIAooAiQgCigCEEECdGogGzYCACAKKAIMKAIUIRwgCigCICAKKAIQQQJ0aiAcNgIAIAooAgwoAhghHSAKKAIcIAooAhBBAnRqIB02AgAgCigCDCgCHCEeIAooAhggCigCEEECdGogHjYCACAKIAooAhBBAWo2AhAMAAsLDwvOAQIBfwF8I4CAgIAAQSBrIQQgBCSAgICAACAEIAA2AhwgBCABNgIYIAQgAjkDECAEIAM2AgwgBCAEKAIcNgIIIAQgBCgCCCgCmAEgBCgCGEGQAWxqNgIEIARBADYCAAJAA0AgBCgCACAEKAIEKAKAAUhBAXFFDQEgBCgCCCAEKAIEKAKEASAEKAIAQSxsaigCKCAEKwMQEMOAgIAAIQUgBCgCDCAEKAIAQQN0aiAFOQMAIAQgBCgCAEEBajYCAAwACwsgBEEgaiSAgICAAA8LwAECAX8DfCOAgICAAEEgayEDIAMkgICAgAAgAyAANgIcIAMgATYCGCADIAI5AxAgA0EAtzkDCCADQQA2AgQCQANAIAMoAgQgAygCHCgCUEhBAXFFDQEgAygCGCADKAIEQQN0aisDACEEIAMoAhxB1ABqIAMoAgRBAnRqKAIAIAMrAxAQvYCAgAAhBSADIAMrAwggBCAFoqA5AwggAyADKAIEQQFqNgIEDAALCyADKwMIIQYgA0EgaiSAgICAACAGDwtzAQJ/I4CAgIAAQRBrIQIgAiAANgIMIAIgATYCCCACIAIoAgw2AgQCQAJAAkAgAigCCEEASEEBcQ0AIAIoAgggAigCBCgClAFOQQFxRQ0BC0F/IQMMAQsgAigCBCgCmAEgAigCCEGQAWxqKAJAIQMLIAMPC2QBAn8jgICAgABBEGshAiACIAA2AgwgAiABNgIIIAIgAigCDCgCmAEgAigCCEGQAWxqNgIEAkACQCACKAIEKAKIAUEAR0EBcUUNACACKAIEKAKIASgCACEDDAELQX8hAwsgAw8LmgEBAn8jgICAgABBIGshAyADIAA2AhwgAyABNgIYIAMgAjYCFCADIAMoAhwoApgBIAMoAhhBkAFsaigCiAE2AhAgA0EANgIMAkADQCADKAIMIAMoAhAoAgBIQQFxRQ0BIAMoAhAoAgggAygCDEECdGooAgAhBCADKAIUIAMoAgxBAnRqIAQ2AgAgAyADKAIMQQFqNgIMDAALCw8LnAECAX8BfCOAgICAAEEgayEDIAMgADYCHCADIAE2AhggAyACNgIUIAMgAygCHCgCmAEgAygCGEGQAWxqKAKIATYCECADQQA2AgwCQANAIAMoAgwgAygCECgCAEhBAXFFDQEgAygCECgCBCADKAIMQQN0aisDACEEIAMoAhQgAygCDEEDdGogBDkDACADIAMoAgxBAWo2AgwMAAsLDwtgAQJ/I4CAgIAAQRBrIQIgAiAANgIMIAIgATYCCCACIAIoAgwoApgBIAIoAghBkAFsaigCiAE2AgQCQAJAIAIoAgRBAEdBAXFFDQAgAigCBCgCECEDDAELQX8hAwsgAw8LbgEBfyOAgICAAEEgayEEIAQgADYCHCAEIAE2AhggBCACNgIUIAQgAzYCECAEIAQoAhwoApgBIAQoAhhBkAFsaigCiAE2AgwgBCgCDCgCFCAEKAIMKAIMIAQoAhRBAnRqKAIAIAQoAhBqQQZ0ag8L4AoGB38BfAR/AXwBfwF8I4CAgIAAQfAAayEFIAUkgICAgAAgBSAANgJkIAUgATYCYCAFIAI2AlwgBSADOQNQIAUgBDYCTCAFIAUoAmQ2AkgCQAJAAkAgBSgCYEEASEEBcQ0AIAUoAmAgBSgCSCgClAFOQQFxRQ0BCyAFRAAAAAAAAPh/OQNoDAELIAUgBSgCSCgCmAEgBSgCYEGQAWxqNgJEAkAgBSgCRCgCiAFBAEdBAXENACAFRAAAAAAAAPh/OQNoDAELIAUgBSgCRCgCiAE2AkAgBSAFKAJAKAIcQQN0EMyBgIAANgI8IAUgBSgCQCgCKDYCOAJAAkAgBSgCOEUNACAFKAI4IQYMAQtBASEGCyAFIAZBAnQQzIGAgAA2AjQCQAJAIAUoAjhFDQAgBSgCOCEHDAELQQEhBwsgBSAHQQJ0EMyBgIAANgIwAkACQCAFKAI4RQ0AIAUoAjghCAwBC0EBIQgLIAUgCEECdBDMgYCAADYCLAJAAkAgBSgCOEUNACAFKAI4IQkMAQtBASEJCyAFIAlBAnQQzIGAgAA2AigCQAJAIAUoAjhFDQAgBSgCOCEKDAELQQEhCgsgBSAKQQN0EMyBgIAANgIkAkACQCAFKAI4RQ0AIAUoAjghCwwBC0EBIQsLIAUgCyAFKAJAKAIAbEECdBDMgYCAADYCIAJAAkAgBSgCPEEAR0EBcUUNACAFKAI0QQBHQQFxRQ0AIAUoAjBBAEdBAXFFDQAgBSgCLEEAR0EBcUUNACAFKAIoQQBHQQFxRQ0AIAUoAiRBAEdBAXFFDQAgBSgCIEEAR0EBcQ0BCyAFKAI8EM6BgIAAIAUoAjQQzoGAgAAgBSgCMBDOgYCAACAFKAIsEM6BgIAAIAUoAigQzoGAgAAgBSgCJBDOgYCAACAFKAIgEM6BgIAAIAVEAAAAAAAA+H85A2gMAQsgBUEANgIcAkADQCAFKAIcIAUoAkAoAhxIQQFxRQ0BIAUoAkggBSgCQCgCICAFKAIcQYgBbGogBSsDUBC8gICAACEMIAUoAjwgBSgCHEEDdGogDDkDACAFIAUoAhxBAWo2AhwMAAsLIAVBADYCGAJAA0AgBSgCGCAFKAI4SEEBcUUNASAFIAUoAkAoAiwgBSgCGEEYbGo2AhQgBSgCFCgCACENIAUoAjQgBSgCGEECdGogDTYCACAFKAIUKAIEIQ4gBSgCMCAFKAIYQQJ0aiAONgIAIAUoAhQoAgghDyAFKAIsIAUoAhhBAnRqIA82AgAgBSgCFCgCDCEQIAUoAiggBSgCGEECdGogEDYCACAFKAJIIAUoAhQoAhAgBSsDUBDDgICAACERIAUoAiQgBSgCGEEDdGogETkDACAFQQA2AhACQANAIAUoAhAgBSgCQCgCAEhBAXFFDQEgBSgCFCgCFCAFKAIQQQJ0aigCACESIAUoAiAgBSgCGCAFKAJAKAIAbCAFKAIQakECdGogEjYCACAFIAUoAhBBAWo2AhAMAAsLIAUgBSgCGEEBajYCGAwACwsgBSAFKwNQIAUoAkAoAgAgBSgCQCgCBCAFKAJAKAIIIAUoAkAoAgwgBSgCXCAFKAJAKAIYIAUoAkAoAhwgBSgCQCgCJCAFKAI8IAUoAjggBSgCNCAFKAIwIAUoAiwgBSgCKCAFKAIkIAUoAiAgBSgCTBDegICAADkDCCAFKAI8EM6BgIAAIAUoAjQQzoGAgAAgBSgCMBDOgYCAACAFKAIsEM6BgIAAIAUoAigQzoGAgAAgBSgCJBDOgYCAACAFKAIgEM6BgIAAIAUgBSsDCDkDaAsgBSsDaCETIAVB8ABqJICAgIAAIBMPCyABAX8jgICAgABBEGshASABIAA2AgwgASgCDCgCnAEPCzEBAX8jgICAgABBEGshAiACIAA2AgwgAiABNgIIIAIoAgwoAqABIAIoAghBiAFsag8LawIBfwF8I4CAgIAAQSBrIQMgAySAgICAACADIAA2AhwgAyABNgIYIAMgAjkDECADIAMoAhw2AgwgAygCDCADKAIMKAKgASADKAIYQYgBbGogAysDEBC8gICAACEEIANBIGokgICAgAAgBA8LVQEBfyOAgICAAEEQayECIAIgADYCDCACIAE2AgggAiACKAIMIAIoAgxBAWpsQQJtNgIEIAIgAigCCCACKAIIQQFqbEECbTYCACACKAIEIAIoAgBsDwvwAgEFfyOAgICAAEEwayEGIAYgADYCLCAGIAE2AiggBiACNgIkIAYgAzYCICAGIAQ2AhwgBiAFNgIYIAZBADYCFCAGQQA2AhACQANAIAYoAhAgBigCLEhBAXFFDQEgBiAGKAIQNgIMAkADQCAGKAIMIAYoAixIQQFxRQ0BIAZBADYCCAJAA0AgBigCCCAGKAIoSEEBcUUNASAGIAYoAgg2AgQCQANAIAYoAgQgBigCKEhBAXFFDQEgBigCECEHIAYoAiQgBigCFEECdGogBzYCACAGKAIMIQggBigCICAGKAIUQQJ0aiAINgIAIAYoAgghCSAGKAIcIAYoAhRBAnRqIAk2AgAgBigCBCEKIAYoAhggBigCFEECdGogCjYCACAGIAYoAhRBAWo2AhQgBiAGKAIEQQFqNgIEDAALCyAGIAYoAghBAWo2AggMAAsLIAYgBigCDEEBajYCDAwACwsgBiAGKAIQQQFqNgIQDAALCw8LhQEBA38jgICAgABBEGshAiACJICAgIAAIAIgADYCDCACIAE2AggCQAJAIAIoAghFDQAgAigCCCEDDAELQQEhAwsgAiADQQEQz4GAgAA2AgQCQCACKAIEQQBHQQFxDQAgAigCDEGJgISAABDXgICAAAsgAigCBCEEIAJBEGokgICAgAAgBA8L7AYDB38BfAR/I4CAgIAAQTBrIQQgBCSAgICAACAEIAA2AiwgBCABNgIoIAQgAjYCJCAEIAM2AiAgBCAEKAIsENiAgIAANgIcIAQgBCgCLBDYgICAADYCGAJAAkAgBCgCHEEBSEEBcQ0AIAQoAhxBgAJKQQFxRQ0BCyAEKAIsQb+AhIAAENeAgIAACwJAAkAgBCgCGEEASEEBcQ0AIAQoAhhBgAJKQQFxRQ0BCyAEKAIsQdWBhIAAENeAgIAACyAEQQA2AhQCQANAIAQoAhQgBCgCGEhBAXFFDQEgBCgCLBDYgICAACEFIAQoAiQgBCgCFEECdGogBTYCACAEIAQoAhRBAWo2AhQMAAsLIAQoAhghBiAEKAIgIAY2AgAgBCgCLBDYgICAACEHIAQoAiggBzYCnAEgBCgCHCEIIAQoAiggCDYCACAEKAIsIAQoAhxBBnQQ0ICAgAAhCSAEKAIoIAk2AgQgBCgCLCAEKAIcQQN0ENCAgIAAIQogBCgCKCAKNgIIIARBADYCEAJAA0AgBCgCECAEKAIcSEEBcUUNASAEKAIsIAQoAigoAgQgBCgCEEEGdGoQ0oCAgAAgBCAEKAIQQQFqNgIQDAALCyAEQQA2AgwCQANAIAQoAgwgBCgCHEhBAXFFDQEgBCgCLBDUgICAACELIAQoAigoAgggBCgCDEEDdGogCzkDACAEIAQoAgxBAWo2AgwMAAsLIAQoAiwQ2ICAgAAhDCAEKAIoIAw2AgwCQAJAIAQoAigoAgxBAUhBAXENACAEKAIoKAIMQRBKQQFxRQ0BCyAEKAIsQaGBhIAAENeAgIAACyAEQQA2AggCQANAIAQoAgggBCgCKCgCDEhBAXFFDQEgBCgCLBDYgICAACENIAQoAihBEGogBCgCCEECdGogDTYCACAEIAQoAghBAWo2AggMAAsLIAQoAiwQ2ICAgAAhDiAEKAIoIA42AlACQAJAIAQoAigoAlBBAUhBAXENACAEKAIoKAJQQRBKQQFxRQ0BCyAEKAIsQYuBhIAAENeAgIAACyAEQQA2AgQCQANAIAQoAgQgBCgCKCgCUEhBAXFFDQEgBCgCLBDYgICAACEPIAQoAihB1ABqIAQoAgRBAnRqIA82AgAgBCAEKAIEQQFqNgIEDAALCyAEQTBqJICAgIAADwuhAQEEfyOAgICAAEEQayECIAIkgICAgAAgAiAANgIMIAIgATYCCCACIAIoAgwQ2YCAgAA2AgQgAiACKAIEEJmBgIAANgIAAkAgAigCAEHAAE9BAXFFDQAgAkE/NgIACyACKAIIIQMgAigCBCEEIAIoAgAhBQJAIAVFDQAgAyAEIAX8CgAACyACKAIIIAIoAgBqQQA6AAAgAkEQaiSAgICAAA8Lih4RBH8BfAN/A3wIfwF8AX8BfAh/AXwFfwR8Cn8BfgV/AXwFfyOAgICAAEHwAmshBCAEJICAgIAAIAQgADYC7AIgBCABNgLoAiAEIAI2AuQCIAQgAzYC4AIgBCgC4AJBjYiEgAAQloGAgAAhBUEBIQZBACAGIAUbIQcgBCgC5AIgBzYCRAJAIAQoAuQCKAJEDQAgBCgC7AIQ1ICAgAAhCCAEKALkAiAIOQNICyAEKALsAhDYgICAACEJIAQoAuQCIAk2AlggBCgC7AIQ2ICAgAAhCiAEKALkAiAKNgJcAkACQCAEKALkAigCWEEBSEEBcQ0AIAQoAuQCKAJcQQFIQQFxRQ0BCyAEKALsAkHZgISAABDXgICAAAsgBCgC7AIgBCgC5AIoAlhBiAFsENCAgIAAIQsgBCgC5AIgCzYCeCAEQQA2AtwCAkADQCAEKALcAiAEKALkAigCWEhBAXFFDQEgBCAEKALkAigCeCAEKALcAkGIAWxqNgLYAiAEKALsAiAEKALYAiAEKALoAigCACAEKALoAigCDBDWgICAACAEQQA2AtQCAkADQCAEKALUAkEFSEEBcUUNASAEKALsAhDUgICAACEMIAQoAtgCQdAAaiAEKALUAkEDdGogDDkDACAEIAQoAtQCQQFqNgLUAgwACwsCQAJAIAQoAuQCKAJEQQFGQQFxRQ0AIAQoAuwCENSAgIAAIQ0MAQsgBCgC5AIrA0ghDQsgDSEOIAQoAtgCIA45A3ggBCAEKALcAkEBajYC3AIMAAsLIAQoAuwCENiAgIAAIQ8gBCgC5AIgDzYCUCAEKALsAhDYgICAACEQIAQoAuQCIBA2AlQCQAJAIAQoAuQCKAJQQQFIQQFxDQAgBCgC5AIoAlRBAUhBAXFFDQELIAQoAuwCQY+EhIAAENeAgIAACwJAIAQoAuQCKAJYIAQoAuQCKAJQIAQoAuQCKAJUbEdBAXFFDQAgBCgC7AJB5IOEgAAQ14CAgAALIAQoAuwCIAQoAuQCKAJQQQZ0ENCAgIAAIREgBCgC5AIgETYCYCAEKALsAiAEKALkAigCVEEGdBDQgICAACESIAQoAuQCIBI2AmQgBCgC7AIgBCgC5AIoAlBBA3QQ0ICAgAAhEyAEKALkAiATNgJoIAQoAuwCIAQoAuQCKAJUQQN0ENCAgIAAIRQgBCgC5AIgFDYCbCAEKALsAiAEKALkAigCUEECdBDQgICAACEVIAQoAuQCIBU2AnAgBCgC7AIgBCgC5AIoAlRBAnQQ0ICAgAAhFiAEKALkAiAWNgJ0IARBADYC0AICQANAIAQoAtACIAQoAuQCKAJQSEEBcUUNASAEKALsAiAEKALkAigCYCAEKALQAkEGdGoQ0oCAgAAgBCAEKALQAkEBajYC0AIMAAsLIARBADYCzAICQANAIAQoAswCIAQoAuQCKAJUSEEBcUUNASAEKALsAiAEKALkAigCZCAEKALMAkEGdGoQ0oCAgAAgBCAEKALMAkEBajYCzAIMAAsLIARBADYCyAICQANAIAQoAsgCIAQoAuQCKAJQSEEBcUUNASAEKALsAhDUgICAACEXIAQoAuQCKAJoIAQoAsgCQQN0aiAXOQMAIAQgBCgCyAJBAWo2AsgCDAALCyAEQQA2AsQCAkADQCAEKALEAiAEKALkAigCUEhBAXFFDQEgBCgC7AIQ2ICAgAAhGCAEKALkAigCcCAEKALEAkECdGogGDYCACAEIAQoAsQCQQFqNgLEAgwACwsgBEEANgLAAgJAA0AgBCgCwAIgBCgC5AIoAlRIQQFxRQ0BIAQoAuwCENSAgIAAIRkgBCgC5AIoAmwgBCgCwAJBA3RqIBk5AwAgBCAEKALAAkEBajYCwAIMAAsLIARBADYCvAICQANAIAQoArwCIAQoAuQCKAJUSEEBcUUNASAEKALsAhDYgICAACEaIAQoAuQCKAJ0IAQoArwCQQJ0aiAaNgIAIAQgBCgCvAJBAWo2ArwCDAALCyAEIAQoAuQCKAJQIAQoAuQCKAJUbDYCuAIgBCAEKALsAiAEKAK4AkECdBDQgICAADYCtAIgBCAEKALsAiAEKAK4AkECdBDQgICAADYCsAIgBEEANgKsAgJAA0AgBCgCrAIgBCgCuAJIQQFxRQ0BIAQoAuwCENiAgIAAIRsgBCgCtAIgBCgCrAJBAnRqIBs2AgAgBCAEKAKsAkEBajYCrAIMAAsLIARBADYCqAICQANAIAQoAqgCIAQoArgCSEEBcUUNASAEKALsAhDYgICAACEcIAQoArACIAQoAqgCQQJ0aiAcNgIAIAQgBCgCqAJBAWo2AqgCDAALCyAEQQA2AqQCAkADQCAEKAKkAiAEKALkAigCWEhBAXFFDQEgBCgCtAIgBCgCpAJBAnRqKAIAQQFrIR0gBCgC5AIoAnggBCgCpAJBiAFsaiAdNgKAASAEKAKwAiAEKAKkAkECdGooAgBBAWshHiAEKALkAigCeCAEKAKkAkGIAWxqIB42AoQBIAQgBCgCpAJBAWo2AqQCDAALCyAEKAK0AhDOgYCAACAEKAKwAhDOgYCAACAEKALsAiAEKALkAigCXEEwbBDQgICAACEfIAQoAuQCIB82AnwgBEEANgKgAgJAA0AgBCgCoAIgBCgC5AIoAlxIQQFxRQ0BIARBADYC7AECQANAIAQoAuwBQQRIQQFxRQ0BIAQoAuwCENiAgIAAISAgBCgC7AEhISAEQZACaiAhQQJ0aiAgNgIAIAQgBCgC7AFBAWo2AuwBDAALCyAEQQA2AugBAkADQCAEKALoAUEESEEBcUUNASAEKALsAhDUgICAACEiIAQoAugBISMgBEHwAWogI0EDdGogIjkDACAEIAQoAugBQQFqNgLoAQwACwsgBCAEKAKQAkEBazYC5AEgBCAEKAKUAkEBazYC4AEgBCAEKAKYAkEBayAEKALkAigCUGs2AtwBIAQgBCgCnAJBAWsgBCgC5AIoAlBrNgLYASAEIAQrA/ABOQPQASAEIAQrA/gBOQPIASAEIAQrA4ACOQPAASAEIAQrA4gCOQO4AQJAIAQoAuQBIAQoAuABSkEBcUUNACAEIAQoAuQBNgK0ASAEIAQoAuABNgLkASAEIAQoArQBNgLgASAEIAQrA9ABOQOoASAEIAQrA8gBOQPQASAEIAQrA6gBOQPIAQsCQCAEKALcASAEKALYAUpBAXFFDQAgBCAEKALcATYCpAEgBCAEKALYATYC3AEgBCAEKAKkATYC2AEgBCAEKwPAATkDmAEgBCAEKwO4ATkDwAEgBCAEKwOYATkDuAELIAQgBCgC5AIoAnwgBCgCoAJBMGxqNgKUASAEKALkASEkIAQoApQBICQ2AgAgBCgC4AEhJSAEKAKUASAlNgIEIAQoAtwBISYgBCgClAEgJjYCCCAEKALYASEnIAQoApQBICc2AgwgBCsD0AEhKCAEKAKUASAoOQMQIAQrA8gBISkgBCgClAEgKTkDGCAEKwPAASEqIAQoApQBICo5AyAgBCsDuAEhKyAEKAKUASArOQMoIAQgBCgCoAJBAWo2AqACDAALCyAEQQg2ApABIARBADYCjAEgBCgC7AIgBCgCkAFBLGwQ0ICAgAAhLCAEKALkAiAsNgKEAQJAA0AgBCAEKALsAhDYgICAADYCiAECQCAEKAKIAQ0ADAILAkAgBCgCiAFBAEhBAXFFDQAgBEEANgKEAQJAA0AgBCgChAEhLSAEKAKIASEuIC1BACAua0hBAXFFDQEgBEEANgKAAQJAA0AgBCgCgAFBCkhBAXFFDQEgBCgC7AIQ2YCAgAAaIAQgBCgCgAFBAWo2AoABDAALCyAEIAQoAoQBQQFqNgKEAQwACwsMAgsCQCAEKAKMASAEKAKQAUZBAXFFDQAgBCAEKAKQAUEBdDYCkAEgBCAEKALsAiAEKAKQAUEsbBDQgICAADYCfCAEKAJ8IS8gBCgC5AIoAoQBITAgBCgCjAFBLGwhMQJAIDFFDQAgLyAwIDH8CgAACyAEKALkAigChAEQzoGAgAAgBCgCfCEyIAQoAuQCIDI2AoQBCyAEKALkAigChAEhMyAEKAKMASE0IAQgNEEBajYCjAEgBCAzIDRBLGxqNgJ4IAQoAnghNUIAITYgNSA2NwIAIDVBKGpBADYCACA1QSBqIDY3AgAgNUEYaiA2NwIAIDVBEGogNjcCACA1QQhqIDY3AgAgBCgC7AIgBEEwahDSgICAACAELQAwITcgBCgCeCA3OgAAIARBADYCHAJAA0AgBCgCHEEESEEBcUUNASAEKALsAhDYgICAACE4IAQoAhwhOSAEQSBqIDlBAnRqIDg2AgAgBCAEKAIcQQFqNgIcDAALCyAEQQA2AhgCQANAIAQoAhhBBEhBAXFFDQEgBCgC7AIQ2ICAgAAhOiAEKAJ4QRhqIAQoAhhBAnRqIDo2AgAgBCAEKAIYQQFqNgIYDAALCyAEQQA2AhQCQANAIAQoAhRBDEhBAXFFDQEgBCgC7AIQ1ICAgAAaIAQgBCgCFEEBajYCFAwACwsgBCgC7AIQ2ICAgAAaIAQoAuwCENiAgIAAGiAEKALsAiAEKALoAigCUEEDdBDQgICAACE7IAQoAnggOzYCKCAEQQA2AhACQANAIAQoAhAgBCgC6AIoAlBIQQFxRQ0BIAQoAuwCENSAgIAAITwgBCgCeCgCKCAEKAIQQQN0aiA8OQMAIAQgBCgCEEEBajYCEAwACwsgBCAEKAIgQQFrNgIMIAQgBCgCJEEBazYCCCAEIAQoAihBAWsgBCgC5AIoAlBrNgIEIAQgBCgCLEEBayAEKALkAigCUGs2AgAgBCgCDCE9IAQoAnggPTYCCCAEKAIIIT4gBCgCeCA+NgIMIAQoAgQhPyAEKAJ4ID82AhAgBCgCACFAIAQoAnggQDYCFAJAAkAgBCgCDCAEKAIIR0EBcUUNACAEKAIEIAQoAgBGQQFxRQ0AIAQoAnhBADYCBAwBCwJAAkAgBCgCDCAEKAIIRkEBcUUNACAEKAIEIAQoAgBHQQFxRQ0AIAQoAnhBATYCBAwBCyAEKAJ4QX82AgQLCwwACwsgBCgCjAEhQSAEKALkAiBBNgKAASAEQfACaiSAgICAAA8LhwECA38BfCOAgICAAEEgayEBIAEkgICAgAAgASAANgIcIAEgASgCHBDZgICAADYCGCABIAEoAhggAUEUahCqgYCAADkDCCABKAIULQAAIQJBGCEDAkAgAiADdCADdUUNACABKAIcQc6DhIAAENeAgIAACyABKwMIIQQgAUEgaiSAgICAACAEDwuCHAgKfwF8B38CfCR/AX4JfwF8I4CAgIAAQbALayEEIAQkgICAgAAgBCAANgKsCyAEIAE2AqgLIAQgAjYCpAsgBCADNgKgCyAEKAKkC0EBNgJAIAQoAqQLQX82AkQgBCAEKAKsC0EwENCAgIAANgKcCyAEKAKcCyEFIAQoAqQLIAU2AogBIAREAAAAAAAA8D85A5ALIAQgBCgCpAtBOhCUgYCAADYCjAsCQCAEKAKMC0EAR0EBcUUNACAEKAKMCy0AASEGQRghByAGIAd0IAd1RQ0AIAQgBCgCjAtBAWpBABCqgYCAADkDkAsLIAQoAqALIQggBCgCnAsgCDYCHCAEKAKsCyAEKAKgC0GIAWwQ0ICAgAAhCSAEKAKcCyAJNgIgIARBADYCiAsCQANAIAQoAogLIAQoAqALSEEBcUUNASAEKAKsCyAEKAKcCygCICAEKAKIC0GIAWxqIAQoAqgLKAIAIAQoAqgLKAIMENaAgIAAIAQgBCgCiAtBAWo2AogLDAALCyAEKAKsCxDYgICAACEKIAQoApwLIAo2AgACQCAEKAKcCygCAEEBSEEBcUUNACAEKAKsC0HHgoSAABDXgICAAAsgBCgCrAsgBCgCnAsoAgBBA3QQ0ICAgAAhCyAEKAKcCyALNgIEIAQoAqwLIAQoApwLKAIAQQJ0ENCAgIAAIQwgBCgCnAsgDDYCCCAEKAKsCyAEKAKcCygCAEECdBDQgICAACENIAQoApwLIA02AgwgBEEANgKECwJAA0AgBCgChAsgBCgCnAsoAgBIQQFxRQ0BIAQrA5ALIAQoAqwLENSAgIAAoiEOIAQoApwLKAIEIAQoAoQLQQN0aiAOOQMAIAQgBCgChAtBAWo2AoQLDAALCyAEQQA2AoALAkADQCAEKAKACyAEKAKcCygCAEhBAXFFDQEgBCgCrAsQ2ICAgAAhDyAEKAKcCygCCCAEKAKAC0ECdGogDzYCAAJAIAQoApwLKAIIIAQoAoALQQJ0aigCAEEBSEEBcUUNACAEKAKsC0H2gYSAABDXgICAAAsgBCAEKAKAC0EBajYCgAsMAAsLIAQoApwLQQA2AhAgBEEANgL8CgJAA0AgBCgC/AogBCgCnAsoAgBIQQFxRQ0BIAQoApwLKAIQIRAgBCgCnAsoAgwgBCgC/ApBAnRqIBA2AgAgBCgCnAsoAgggBCgC/ApBAnRqKAIAIREgBCgCnAshEiASIBEgEigCEGo2AhAgBCAEKAL8CkEBajYC/AoMAAsLIAQoAqwLIAQoApwLKAIQQQZ0ENCAgIAAIRMgBCgCnAsgEzYCFCAEKAKsCyAEKAKcCygCEEEDdBDQgICAACEUIAQoApwLIBQ2AhggBEEANgL4CgJAA0AgBCgC+AogBCgCnAsoAgBIQQFxRQ0BIARBADYC9AoCQANAIAQoAvQKIAQoApwLKAIIIAQoAvgKQQJ0aigCAEhBAXFFDQEgBCAEKAKcCygCFCAEKAKcCygCDCAEKAL4CkECdGooAgAgBCgC9ApqQQZ0ajYC8AogBCgCrAsgBCgC8AoQ0oCAgAAgBCgC8ApBqoiEgAAQloGAgAAhFUEAtyEWRAAAAAAAAPA/IBYgFRshFyAEKAKcCygCGCAEKAKcCygCDCAEKAL4CkECdGooAgAgBCgC9ApqQQN0aiAXOQMAIAQgBCgC9ApBAWo2AvQKDAALCyAEIAQoAvgKQQFqNgL4CgwACwsgBCAEKAKcCygCHDYC7AogBCgCrAsgBCgC7AogBCgCnAsoAgBsQQJ0ENCAgIAAIRggBCgCnAsgGDYCJCAEQQA2AugKAkADQCAEKALoCiAEKAKcCygCAEhBAXFFDQEgBEEANgLkCgJAA0AgBCgC5AogBCgC7ApIQQFxRQ0BIAQoAqwLENiAgIAAQQFrIRkgBCgCnAsoAiQgBCgC5AogBCgCnAsoAgBsIAQoAugKakECdGogGTYCACAEIAQoAuQKQQFqNgLkCgwACwsgBCAEKALoCkEBajYC6AoMAAsLAkAgBCgCnAsoAgBBwABKQQFxRQ0AIAQoAqwLQbKChIAAENeAgIAACyAEQQA2AtwIIARBADYC2AgCQANAIAQoAtgIIAQoApwLKAIASEEBcUUNASAEIAQoApwLKAIIIAQoAtgIQQJ0aigCACAEKALcCGo2AtwIIAQoAtwIIRogBCgC2AghGyAEQeAIaiAbQQJ0aiAaNgIAIAQgBCgC2AhBAWo2AtgIDAALCyAEQQg2AtQIIAQoApwLQQA2AiggBCgCrAsgBCgC1AhBGGwQ0ICAgAAhHCAEKAKcCyAcNgIsAkADQCAEIAQoAqwLENiAgIAANgLQCAJAIAQoAtAIDQAMAgsCQCAEKALQCEEASEEBcUUNACAEKAKsC0GjhISAABDXgICAAAsgBEEANgJMAkADQCAEKAJMIAQoApwLKAIASEEBcUUNASAEKAJMIR0gBEHQBmogHUECdGpBfzYCACAEKAJMIR4gBEHQAGogHkECdGpBADYCACAEIAQoAkxBAWo2AkwMAAsLIARBADYCSAJAA0AgBCgCSCAEKALQCEhBAXFFDQEgBCAEKAKsCxDYgICAADYCRCAEQQA2AkADQCAEKAJAIAQoApwLKAIASCEfQQAhICAfQQFxISEgICEiAkAgIUUNACAEKAJAISMgBEHgCGogI0ECdGooAgAgBCgCREghIgsCQCAiQQFxRQ0AIAQgBCgCQEEBajYCQAwBCwsCQCAEKAJAIAQoApwLKAIATkEBcUUNACAEKAKsC0HnhISAABDXgICAAAsCQAJAIAQoAkANAEEAISQMAQsgBCgCQEEBayElIARB4AhqICVBAnRqKAIAISQLIAQgJDYCPCAEIAQoAkQgBCgCPGtBAWs2AjgCQAJAIAQoAjhBAEhBAXENACAEKAI4IAQoApwLKAIIIAQoAkBBAnRqKAIATkEBcUUNAQsgBCgCrAtB54SEgAAQ14CAgAALIAQoAkAhJgJAAkAgBEHQAGogJkECdGooAgANACAEKAI4IScgBCgCQCEoIARB0ARqIChBAnRqICc2AgAgBCgCOCEpIAQoAkAhKiAEQdAGaiAqQQJ0aiApNgIADAELIAQoAkAhKwJAAkAgBEHQAGogK0ECdGooAgBBAUZBAXFFDQAgBCgCOCEsIAQoAkAhLSAEQdACaiAtQQJ0aiAsNgIADAELIAQoAqwLQcqGhIAAENeAgIAACwsgBCgCQCEuIARB0ABqIC5BAnRqIS8gLyAvKAIAQQFqNgIAIAQgBCgCSEEBajYCSAwACwsgBEF/NgI0IARBADYCMAJAA0AgBCgCMCAEKAKcCygCAEhBAXFFDQEgBCgCMCEwAkACQCAEQdAAaiAwQQJ0aigCAEECRkEBcUUNAAJAIAQoAjRBAE5BAXFFDQAgBCgCrAtBgoeEgAAQ14CAgAALIAQgBCgCMDYCNAwBCyAEKAIwITECQCAEQdAAaiAxQQJ0aigCAEEBR0EBcUUNACAEKAKsC0GBg4SAABDXgICAAAsLIAQgBCgCMEEBajYCMAwACwsCQCAEKAI0QQBIQQFxRQ0AIAQoAqwLQY2FhIAAENeAgIAACyAEKAI0ITIgBCAEQdAEaiAyQQJ0aigCADYCLCAEKAI0ITMgBCAEQdACaiAzQQJ0aigCADYCKAJAIAQoApwLKAIUIAQoApwLKAIMIAQoAjRBAnRqKAIAIAQoAixqQQZ0aiAEKAKcCygCFCAEKAKcCygCDCAEKAI0QQJ0aigCACAEKAIoakEGdGoQloGAgABBAEpBAXFFDQAgBCAEKAIsNgIkIAQgBCgCKDYCLCAEIAQoAiQ2AigLIAQgBCgCrAsQ2ICAgAA2AiACQCAEKAIgQQBIQQFxRQ0AIAQoAqwLQfOAhIAAENeAgIAACyAEQQA2AhwCQANAIAQoAhwgBCgCIEhBAXFFDQECQCAEKAKcCygCKCAEKALUCEZBAXFFDQAgBCAEKALUCEEBdDYC1AggBCAEKAKsCyAEKALUCEEYbBDQgICAADYCGCAEKAIYITQgBCgCnAsoAiwhNSAEKAKcCygCKEEYbCE2AkAgNkUNACA0IDUgNvwKAAALIAQoApwLKAIsEM6BgIAAIAQoAhghNyAEKAKcCyA3NgIsCyAEKAKcCygCLCE4IAQoApwLITkgOSgCKCE6IDkgOkEBajYCKCAEIDggOkEYbGo2AhQgBCgCFCE7QgAhPCA7IDw3AgAgO0EQaiA8NwIAIDtBCGogPDcCACAEKAI0IT0gBCgCFCA9NgIAIAQoAiwhPiAEKAIUID42AgQgBCgCKCE/IAQoAhQgPzYCCCAEKAIcIUAgBCgCFCBANgIMIAQoAqwLIAQoApwLKAIAQQJ0ENCAgIAAIUEgBCgCFCBBNgIUIARBADYCEAJAA0AgBCgCECAEKAKcCygCAEhBAXFFDQECQAJAIAQoAhAgBCgCNEZBAXFFDQBBACFCDAELIAQoAhAhQyAEQdAGaiBDQQJ0aigCACFCCyBCIUQgBCgCFCgCFCAEKAIQQQJ0aiBENgIAIAQgBCgCEEEBajYCEAwACwsgBCgCrAsgBCgCqAsoAlBBA3QQ0ICAgAAhRSAEKAIUIEU2AhAgBEEANgIMAkADQCAEKAIMIAQoAqgLKAJQSEEBcUUNASAEKAKsCxDUgICAACFGIAQoAhQoAhAgBCgCDEEDdGogRjkDACAEIAQoAgxBAWo2AgwMAAsLIAQgBCgCHEEBajYCHAwACwsMAAsLIARBsAtqJICAgIAADwu3CAMPfwF8Bn8jgICAgABB4AFrIQQgBCSAgICAACAEIAA2AtwBIAQgATYC2AEgBCACNgLUASAEIAM2AtABIAQoAtgBIQVBiAEhBkEAIQcCQCAGRQ0AIAUgByAG/AsACyAEKALcASAEKALYARDSgICAACAEIAQoAtwBENqAgIAANgLMAQJAIAQoAswBQQBHQQFxRQ0AIAQoAswBQeuIhIAAEJaBgIAADQAgBCgC3AEQ2YCAgAAaCwJAAkAgBCgC3AEQ2oCAgAAQ24CAgABFDQAgBCAEKALcARDYgICAADYCyAEMAQsgBCAEKALcARDUgICAADkDwAEgBCAEKALcARDUgICAADkDuAECQAJAIAQrA8ABQQC3YkEBcQ0AIAQrA7gBQQC3YkEBcUUNAQsgBCgC3AFBk4aEgAAQ14CAgAALIAQgBCgC3AEQ2ICAgAA2AsgBCyAEIAQoAsgBQQxKQQFxNgK0ASAEKAK0ASEIIAQoAtgBIAg2AkwCQAJAIAQoArQBRQ0AIAQoAsgBQQxrIQkMAQsgBCgCyAEhCQsgBCAJNgKwAQJAAkAgBCgCsAFBAUhBAXENACAEKAKwAUEGSkEBcUUNAQsgBCgC3AFBu4eEgAAQ14CAgAALIAQoArABQQRGIQpBASELIApBAXEhDCALIQ0CQCAMDQAgBCgCsAFBBUYhDkEBIQ8gDkEBcSEQIA8hDSAQDQAgBCgCsAFBBkYhDQsgBCANQQFxNgKsAQJAAkAgBCgCsAFBAkZBAXENACAEKAKwAUEFRkEBcUUNAQsgBCgC3AFBuIWEgAAQ14CAgAALAkACQCAEKAKwAUEDRkEBcQ0AIAQoArABQQZGQQFxRQ0BCyAEKALcAUHohYSAABDXgICAAAsgBCgC3AEQ2ICAgAAhESAEKALYASARNgJEAkAgBCgC2AEoAkRBAUhBAXFFDQAgBCgC3AFBloKEgAAQ14CAgAALIAQoAtwBIAQoAtQBQQN0ENCAgIAAIRIgBCgC2AEgEjYCQCAEQQA2AqgBAkADQCAEKAKoASAEKALUAUhBAXFFDQEgBCgC3AEQ1ICAgAAhEyAEKALYASgCQCAEKAKoAUEDdGogEzkDACAEIAQoAqgBQQFqNgKoAQwACwsgBCgC3AEgBCgC2AEoAkRBmAFsENCAgIAAIRQgBCgC2AEgFDYCSCAEQQA2AqQBAkADQCAEKAKkASAEKALYASgCREhBAXFFDQEgBCgC2AEoAkggBCgCpAFBmAFsaiEVIAQoAtwBIRYgBCgC0AEhFyAEKAKsASEYIARBCGogFiAXIBgQ3ICAgABBmAEhGQJAIBlFDQAgFSAEQQhqIBn8CgAACyAEIAQoAqQBQQFqNgKkAQwACwsCQCAEKAK0AUUNACAEKALcARDUgICAABogBCgC3AEQ1ICAgAAaCyAEQeABaiSAgICAAA8LdQEEfyOAgICAAEEQayECIAIkgICAgAAgAiAANgIMIAIgATYCCCACKAIMQfABaiEDIAIoAgwoAgghBCACIAIoAgg2AgQgAiAENgIAQfWChIAAIQUgA0GAAiAFIAIQk4GAgAAaIAIoAgxB1ABqQQEQ2oGAgAAAC4cBAQR/I4CAgIAAQRBrIQEgASSAgICAACABIAA2AgwgASABKAIMENmAgIAANgIIIAEgASgCCCABQQRqQQoQrYGAgAA2AgAgASgCBC0AACECQRghAwJAIAIgA3QgA3VFDQAgASgCDEG6g4SAABDXgICAAAsgASgCACEEIAFBEGokgICAgAAgBA8LZAECfyOAgICAAEEQayEBIAEkgICAgAAgASAANgIMIAEgASgCDBDdgICAADYCCAJAIAEoAghBAEdBAXENACABKAIMQdCEhIAAENeAgIAACyABKAIIIQIgAUEQaiSAgICAACACDwvbAgEKfyOAgICAAEEgayEBIAEkgICAgAAgASAANgIYIAEgASgCGCgCBDYCFCABIAEoAhgoAgg2AhAgASABKAIYEN2AgIAANgIMAkACQCABKAIMQQBHQQFxDQAgASgCFCECIAEoAhggAjYCBCABKAIQIQMgASgCGCADNgIIIAFBADYCHAwBCyABIAEoAgwQmYGAgAA2AggCQCABKAIIQcAAT0EBcUUNACABQT82AggLIAEoAhhBEWohBCABKAIMIQUgASgCCCEGAkAgBkUNACAEIAUgBvwKAAALIAEoAhhBEWogASgCCGpBADoAAAJAIAEoAhgoAgxBAEdBAXFFDQAgASgCGC0AECEHIAEoAhgoAgwgBzoAAAsgASgCFCEIIAEoAhggCDYCBCABKAIQIQkgASgCGCAJNgIIIAEgASgCGEERajYCHAsgASgCHCEKIAFBIGokgICAgAAgCg8LzwIBCn8jgICAgABBEGshASABJICAgIAAIAEgADYCCAJAAkAgASgCCEEAR0EBcQ0AIAFBADYCDAwBCyABKAIILQAAIQJBGCEDAkACQCACIAN0IAN1QStGQQFxDQAgASgCCC0AACEEQRghBSAEIAV0IAV1QS1GQQFxRQ0BCyABIAEoAghBAWo2AggLIAEoAggtAAAhBkEAIQcCQCAGQf8BcSAHQf8BcUdBAXENACABQQA2AgwMAQsCQANAIAEoAggtAAAhCEEAIQkgCEH/AXEgCUH/AXFHQQFxRQ0BAkACQAJAQQBBAXFFDQAgASgCCC0AAEH/AXEQ+ICAgAANAgwBCyABKAIILQAAQf8BcUEwa0EKSUEBcQ0BCyABQQA2AgwMAwsgASABKAIIQQFqNgIIDAALCyABQQE2AgwLIAEoAgwhCiABQRBqJICAgIAAIAoPC5QDAgN/A3wjgICAgABBIGshBCAEJICAgIAAIAQgATYCHCAEIAI2AhggBCADNgIUQZgBIQVBACEGAkAgBUUNACAAIAYgBfwLAAsgACAEKAIcENSAgIAAOQMAIARBADYCEAJAA0AgBCgCECAEKAIYSEEBcUUNASAEKAIcENSAgIAAIQcgAEEIaiAEKAIQQQN0aiAHOQMAIAQgBCgCEEEBajYCEAwACwsCQCAEKAIURQ0AIAAgBCgCHBDYgICAADYCiAECQCAAKAKIAUEASEEBcUUNACAEKAIcQbaBhIAAENeAgIAACyAAIAQoAhwgACgCiAFBA3QQ0ICAgAA2AowBIAAgBCgCHCAAKAKIAUEDdBDQgICAADYCkAEgBEEANgIMAkADQCAEKAIMIAAoAogBSEEBcUUNASAEKAIcENSAgIAAIQggACgCjAEgBCgCDEEDdGogCDkDACAEKAIcENSAgIAAIQkgACgCkAEgBCgCDEEDdGogCTkDACAEIAQoAgxBAWo2AgwMAAsLCyAEQSBqJICAgIAADwu9BQEufyOAgICAAEEQayEBIAEgADYCCCABIAEoAggoAgQ2AgQDQANAIAEoAgQtAAAhAkEYIQMgAiADdCADdUEgRiEEQQEhBSAEQQFxIQYgBSEHAkAgBg0AIAEoAgQtAAAhCEEYIQkgCCAJdCAJdUEJRiEKQQEhCyAKQQFxIQwgCyEHIAwNACABKAIELQAAIQ1BGCEOIA0gDnQgDnVBDUYhBwsCQCAHQQFxRQ0AIAEgASgCBEEBajYCBAwBCwsgASgCBC0AACEPQRghEAJAIA8gEHQgEHVBCkZBAXFFDQAgASgCCCERIBEgESgCCEEBajYCCCABIAEoAgRBAWo2AgQMAQsLIAEoAgQtAAAhEkEYIRMCQAJAIBIgE3QgE3UNACABKAIEIRQgASgCCCAUNgIEIAFBADYCDAwBCyABIAEoAgQ2AgADQCABKAIELQAAIRVBGCEWIBUgFnQgFnUhF0EAIRgCQCAXRQ0AIAEoAgQtAAAhGUEYIRogGSAadCAadUEgRyEbQQAhHCAbQQFxIR0gHCEYIB1FDQAgASgCBC0AACEeQRghHyAeIB90IB91QQlHISBBACEhICBBAXEhIiAhIRggIkUNACABKAIELQAAISNBGCEkICMgJHQgJHVBDUchJUEAISYgJUEBcSEnICYhGCAnRQ0AIAEoAgQtAAAhKEEYISkgKCApdCApdUEKRyEYCwJAIBhBAXFFDQAgASABKAIEQQFqNgIEDAELCyABKAIELQAAISpBACErAkACQCAqQf8BcSArQf8BcUdBAXFFDQAgASgCBCEsIAEoAgggLDYCDCABKAIELQAAIS0gASgCCCAtOgAQIAEoAgRBADoAACABIAEoAgRBAWo2AgQMAQsgASgCCEEANgIMCyABKAIEIS4gASgCCCAuNgIEIAEgASgCADYCDAsgASgCDA8LkQsCAX8MfCOAgICAAEHQAWshEiASJICAgIAAIBIgADkDyAEgEiABNgLEASASIAI2AsABIBIgAzYCvAEgEiAENgK4ASASIAU2ArQBIBIgBjYCsAEgEiAHNgKsASASIAg2AqgBIBIgCTYCpAEgEiAKNgKgASASIAs2ApwBIBIgDDYCmAEgEiANNgKUASASIA42ApABIBIgDzYCjAEgEiAQNgKIASASIBE2AoQBIBJBALc5A3ggEkEANgJ0AkADQCASKAJ0IBIoAqwBSEEBcUUNASASRAAAAAAAAPA/OQNoIBJBADYCZAJAA0AgEigCZCASKALEAUhBAXFFDQEgEiASKAK0ASASKAK4ASASKAJkQQJ0aigCACASKAKoASASKAJ0IBIoAsQBbCASKAJkakECdGooAgBqQQN0aisDACASKwNoojkDaCASIBIoAmRBAWo2AmQMAAsLIBIrA2ghEyASKAKkASASKAJ0QQN0aisDACEUIBIgEisDeCAT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AAAgACACaiIDQX9qIAE6AAAgAkEDSQ0AIAAgAToAAiAAIAE6AAEgA0F9aiABOgAAIANBfmogAToAACACQQdJDQAgACABOgADIANBfGogAToAACACQQlJDQAgAEEAIABrQQNxIgRqIgMgAUH/AXFBgYKECGwiATYCACADIAIgBGtBfHEiBGoiAkF8aiABNgIAIARBCUkNACADIAE2AgggAyABNgIEIAJBeGogATYCACACQXRqIAE2AgAgBEEZSQ0AIAMgATYCGCADIAE2AhQgAyABNgIQIAMgATYCDCACQXBqIAE2AgAgAkFsaiABNgIAIAJBaGogATYCACACQWRqIAE2AgAgBCADQQRxQRhyIgVrIgJBIEkNACABrUKBgICAEH4hBiADIAVqIQEDQCABIAY3AxggASAGNwMQIAEgBjcDCCABIAY3AwAgAUEgaiEBIAJBYGoiAkEfSw0ACwsgAAsRACAAKAI8IAEgAhD+gICAAAuBAwEHfyOAgICAAEEgayIDJICAgIAAIAMgACgCHCIENgIQIAAoAhQhBSADIAI2AhwgAyABNgIYIAMgBSAEayIBNgIUIAEgAmohBiADQRBqIQRBAiEHAkACQAJAAkACQCAAKAI8IANBEGpBAiADQQxqEIWAgIAAEMSBgIAARQ0AIAQhBQwBCwNAIAYgAygCDCIBRg0CAkAgAUF/Sg0AIAQhBQwECyAEQQhBACABIAQoAgQiCEsiCRtqIgUgBSgCACABIAhBACAJG2siCGo2AgAgBEEMQQQgCRtqIgQgBCgCACAIazYCACAGIAFrIQYgBSEEIAAoAjwgBSAHIAlrIgcgA0EMahCFgICAABDEgYCAAEUNAAsLIAZBf0cNAQsgACAAKAIsIgE2AhwgACABNgIUIAAgASAAKAIwajYCECACIQEMAQtBACEBIABBADYCHCAAQgA3AxAgACAAKAIAQSByNgIAIAdBAkYNACACIAUoAgRrIQELIANBIGokgICAgAAgAQv2AQEEfyOAgICAAEEgayIDJICAgIAAIAMgATYCEEEAIQQgAyACIAAoAjAiBUEAR2s2AhQgACgCLCEGIAMgBTYCHCADIAY2AhhBICEFAkACQAJAIAAoAjwgA0EQakECIANBDGoQhoCAgAAQxIGAgAANACADKAIMIgVBAEoNAUEgQRAgBRshBQsgACAAKAIAIAVyNgIADAELIAUhBCAFIAMoAhQiBk0NACAAIAAoAiwiBDYCBCAAIAQgBSAGa2o2AggCQCAAKAIwRQ0AIAAgBEEBajYCBCABIAJqQX9qIAQtAAA6AAALIAIhBAsgA0EgaiSAgICAACAECwQAIAALGQAgACgCPBDqgICAABCHgICAABDEgYCAAAuGAwECfyOAgICAAEEgayICJICAgIAAAkACQAJAAkBBiYiEgAAgASwAABCUgYCAAA0AEOSAgIAAQRw2AgAMAQtBmAkQzIGAgAAiAw0BC0EAIQMMAQsgA0EAQZABEOaAgIAAGgJAIAFBKxCUgYCAAA0AIANBCEEEIAEtAABB8gBGGzYCAAsCQAJAIAEtAABB4QBGDQAgAygCACEBDAELAkAgAEEDQQAQg4CAgAAiAUGACHENACACIAFBgAhyrDcDECAAQQQgAkEQahCDgICAABoLIAMgAygCAEGAAXIiATYCAAsgA0F/NgJQIANBgAg2AjAgAyAANgI8IAMgA0GYAWo2AiwCQCABQQhxDQAgAiACQRhqrTcDACAAQZOoASACEISAgIAADQAgA0EKNgJQCyADQYaAgIAANgIoIANBh4CAgAA2AiQgA0GIgICAADYCICADQYmAgIAANgIMAkBBAC0A2fSEgAANACADQX82AkwLIAMQg4GAgAAhAwsgAkEgaiSAgICAACADC50BAQN/I4CAgIAAQRBrIgIkgICAgAACQAJAAkBBiYiEgAAgASwAABCUgYCAAA0AEOSAgIAAQRw2AgAMAQsgARDlgICAACEDIAJCtgM3AwBBACEEQZx/IAAgA0GAgAJyIAIQgoCAgAAQroGAgAAiAEEASA0BIAAgARDsgICAACIEDQEgABCHgICAABoLQQAhBAsgAkEQaiSAgICAACAECxMAIAIEQCAAIAEgAvwKAAALIAALkwQBA38CQCACQYAESQ0AIAAgASACEO6AgIAADwsgACACaiEDAkACQCABIABzQQNxDQACQAJAIABBA3ENACAAIQIMAQsCQCACDQAgACECDAELIAAhAgNAIAIgAS0AADoAACABQQFqIQEgAkEBaiICQQNxRQ0BIAIgA0kNAAsLIANBfHEhBAJAIANBwABJDQAgAiAEQUBqIgVLDQADQCACIAEoAgA2AgAgAiABKAIENgIEIAIgASgCCDYCCCACIAEo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/wCDIgkQ1IGAgABBAEoNAAJAIAEgCCADIAkQ1IGAgABFDQAgASEEDAILIAVB8ABqIAEgAkIAQgAQ5IGAgAAgBSkDeCECIAUpA3AhBAwBCyAEQjCIp0H//wFxIQoCQAJAIAdFDQAgASEEDAELIAVB4ABqIAEgCEIAQoCAgICAgMC7wAAQ5IGAgAAgBSkDaCIIQjCIp0GIf2ohByAFKQNgIQQLAkAgCg0AIAVB0ABqIAMgCUIAQoCAgICAgMC7wAAQ5IGAgAAgBSkDWCIJQjCIp0GIf2ohCiAFKQNQIQMLIAlC////////P4NCgICAgICAwACEIQsgCEL///////8/g0KAgICAgIDAAIQhCAJAIAcgCkwNAANAAkACQCAIIAt9IAQgA1StfSIJQgBTDQACQCAJIAQgA30iBIRCAFINACAFQSBqIAEgAkIAQgAQ5IGAgAAgBSkDKCECIAUpAyAhBAwFCyAJQgGGIARCP4iEIQgMAQsgCEIBhiAEQj+IhCEICyAEQgGGIQQgB0F/aiIHIApKDQALIAohBwsCQAJAIAggC30gBCADVK19IglCAFkNACAIIQkMAQsgCSAEIAN9IgSEQgBSDQAgBUEwaiABIAJCAEIAEOSBgIAAIAUpAzghAiAFKQMwIQQMAQsCQCAJQv///////z9WDQADQCAEQj+IIQMgB0F/aiEHIARCAYYhBCADIAlCAYaEIglCgICAgICAwABUDQALCyAGQYCAAnEhCgJAIAdBAEoNACAFQcAAaiAEIAlC////////P4MgB0H4AGogCnKtQjCGhEIAQoCAgICAgMDDPxDkgYCAACAFKQNIIQIgBSkDQCEEDAELIAlC////////P4MgByAKcq1CMIaEIQILIAAgBDcDACAAIAI3AwggBUGAAWokgICAgAALHAAgACACQv///////////wCDNwMIIAAgATcDAAvZCQQBfwF+Bn8BfiOAgICAAEEwayIEJICAgIAAQgAhBQJAAkAgAkECSw0AIAJBAnQiAigC/NuEgAAhBiACKALw24SAACEHA0ACQAJAIAEoAgQiAiABKAJoRg0AIAEgAkEBajYCBCACLQAAIQIMAQsgARCdgYCAACECCyACEKWBgIAADQALQQEhCAJAAkAgAkFVag4DAAEAAQtBf0EBIAJBLUYbIQgCQCABKAIEIgIgASgCaEYN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ABCKgICAAA0BCxDkgICAAEEwNgIAQX8PC0EAIAA2AsTyhIAAIAELgAsHAX8BfgF/An4BfwF+AX8jgICAgABB8ABrIgUkgICAgAAgBEL///////////8AgyEGAkACQAJAIAFQIgcgAkL///////////8AgyIIQoCAgICAgMCAgH98QoCAgICAgMCAgH9UIAhQGw0AIANCAFIgBkKAgICAgIDAgIB/fCIJQoCAgICAgMCAgH9WIAlCgICAgICAwICAf1EbDQELAkAgByAIQoCAgICAgMD//wBUIAhCgICAgICAwP//AFEbDQAgAkKAgICAgIAghCEEIAEhAwwCCwJAIANQIAZCgICAgICAwP//AFQgBkKAgICAgIDA//8AURsNACAEQoCAgICAgCCEIQQMAgsCQCABIAhCgICAgICAwP//AIWEQgBSDQBCgICAgICA4P//ACACIAMgAYUgBCAChUKAgICAgICAgIB/hYRQIgcbIQRCACABIAcbIQMMAgsgAyAGQoCAgICAgMD//wCFhFANAQJAIAEgCIRCAFINACADIAaEQgBSDQIgAyABgyEDIAQgAoMhBAwCCyADIAaEUEUNACABIQMgAiEEDAELIAMgASADIAFWIAYgCFYgBiAIURsiChshBiAEIAIgChsiCUL///////8/gyEIIAIgBCAKGyILQjCIp0H//wFxIQwCQCAJQjCIp0H//wFxIgcNACAFQeAAaiAGIAggBiAIIAhQIgcbeULAAEIAIAcbfKciB0FxahDTgYCAAEEQIAdrIQcgBSkDaCEIIAUpA2AhBgsgASADIAobIQMgC0L///////8/gyEBAkAgDA0AIAVB0ABqIAMgASADIAEgAVAiCht5QsAAQgAgCht8pyIKQXFqENOBgIAAQRAgCmshDCAFKQNYIQEgBSkDUCEDCyABQgOGIANCPYiEQoCAgICAgIAEhCEBIAhCA4YgBkI9iIQhCyADQgOGIQggBCAChSEDAkAgByAMRg0AAkAgByAMayIKQf8ATQ0AQgAhAUIBIQgMAQsgBUHAAGogCCABQYABIAprENOBgIAAIAVBMGogCCABIAoQ44GAgAAgBSkDMCAFKQNAIAUpA0iEQgBSrYQhCCAFKQM4IQELIAtCgICAgICAgASEIQsgBkIDhiEGAkACQCADQn9VDQBCACEDQgAhBCAGIAiFIAsgAYWEUA0CIAYgCH0hAiALIAF9IAYgCFStfSIEQv////////8DVg0BIAVBIGogAiAEIAIgBCAEUCIKG3lCwABCACAKG3ynQXRqIgoQ04GAgAAgByAKayEHIAUpAyghBCAFKQMgIQIMAQsgASALfCAIIAZ8IgIgCFStfCIEQoCAgICAgIAIg1ANACACQgGIIARCP4aEIAhCAYOEIQIgB0EBaiEHIARCAYghBAsgCUKAgICAgICAgIB/gyEIAkAgB0H//wFIDQAgCEKAgICAgIDA//8AhCEEQgAhAwwBC0EAIQoCQAJAIAdBAEwNACAHIQoMAQsgBUEQaiACIAQgB0H/AGoQ04GAgAAgBSACIARBASAHaxDjgYCAACAFKQMAIAUpAxAgBSkDGIRCAFKthCECIAUpAwghBAsgAkIDiCAEQj2GhCEDIAqtQjCGIARCA4hC////////P4OEIAiEIQQgAqdBB3EhBwJAAkACQAJAAkAQ4YGAgAAOAwABAgMLAkAgB0EERg0AIAQgAyAHQQRLrXwiCCADVK18IQQgCCEDDAMLIAQgAyADQgGDfCIIIANUrXwhBCAIIQMMAwsgBCADIAhCAFIgB0EAR3GtfCIIIANUrXwhBCAIIQMMAQsgBCADIAhQIAdBAEdxrXwiCCADVK18IQQgCCEDCyAHRQ0BCxDigYCAABoLIAAgAzcDACAAIAQ3AwggBUHwAGokgICAgAALUwEBfgJAAkAgA0HAAHFFDQAgASADQUBqrYYhAkIAIQEMAQsgA0UNACABQcAAIANrrYggAiADrSIEhoQhAiABIASGIQELIAAgATcDACAAIAI3AwgL5gECAX8CfkEBIQQCQCAAQgBSIAFC////////////AIMiBUKAgICAgIDA//8AViAFQoCAgICAgMD//wBRGw0AIAJCAFIgA0L///////////8AgyIGQoCAgICAgMD//wBWIAZCgICAgICAwP//AFEbDQACQCACIACEIAYgBYSEUEUNAEEADwsCQCADIAGDQgBTDQACQCAAIAJUIAEgA1MgASADURtFDQBBfw8LIAAgAoUgASADhYRCAFIPCwJAIAAgAlYgASADVSABIANRG0UNAEF/DwsgACAChSABIAOFhEIAUiEECyAEC9gBAgF/An5BfyEEAkAgAEIAUiABQv///////////wCDIgVCgICAgICAwP//AFYgBUKAgICAgIDA//8AURsNACACQgBSIANC////////////AIMiBkKAgICAgIDA//8AViAGQoCAgICAgMD//wBRGw0AAkAgAiAAhCAGIAWEhFBFDQBBAA8LAkAgAyABg0IAUw0AIAAgAlQgASADUyABIANRGw0BIAAgAoUgASADhYRCAFIPCyAAIAJWIAEgA1UgASADURsNACAAIAKFIAEgA4WEQgBSIQQLIAQLxRAGAX8DfgN/AX4Bfwt+I4CAgIAAQdACayIFJICAgIAAIARC////////P4MhBiACQv///////z+DIQcgBCAChUKAgICAgICAgIB/gyEIIARCMIinQf//AXEhCQJAAkACQCACQjCIp0H//wFxIgpBgYB+akGCgH5JDQBBACELIAlBgYB+akGBgH5LDQELAkAgAVAgAkL///////////8AgyIMQoCAgICAgMD//wBUIAxCgICAgICAwP//AFEbDQAgAkKAgICAgIAghCEIDAILAkAgA1AgBEL///////////8AgyICQoCAgICAgMD//wBUIAJCgICAgICAwP//AFEbDQAgBEKAgICAgIAghCEIIAMhAQwCCwJAIAEgDEKAgICAgIDA//8AhYRCAFINAAJAIAMgAkKAgICAgIDA//8AhYRQRQ0AQgAhAUKAgICAgIDg//8AIQgMAwsgCEKAgICAgIDA//8AhCEIQgAhAQwCCwJAIAMgAkKAgICAgIDA//8AhYRCAFINAEIAIQEMAgsCQCABIAyEQgBSDQBCgICAgICA4P//ACAIIAMgAoRQGyEIQgAhAQwCCwJAIAMgAoRCAFINACAIQoCAgICAgMD//wCEIQhCACEBDAILQQAhCwJAIAxC////////P1YNACAFQcACaiABIAcgASAHIAdQIgsbeULAAEIAIAsbfKciC0FxahDTgYCAAEEQIAtrIQsgBSkDyAIhByAFKQPAAiEBCyACQv///////z9WDQAgBUGwAmogAyAGIAMgBiAGUCING3lCwABCACANG3ynIg1BcWoQ04GAgAAgDSALakFwaiELIAUpA7gCIQYgBSkDsAIhAwsgBUGgAmogA0IxiCAGQoCAgICAgMAAhCIOQg+GhCICQgBCgICAgLDmvIL1ACACfSIEQgAQ5YGAgAAgBUGQAmpCACAFKQOoAn1CACAE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JICAgIAAIAG8IgNB////A3EhBAJAAkAgA0EXdiIFQf8BcSIGRQ0AAkAgBkH/AUYNACAErUIZhiEHIAVB/wFxQYD/AGohBEIAIQgMAgsgBK1CGYYhB0IAIQhB//8BIQQMAQsCQCAEDQBCACEIQQAhBEIAIQcMAQsgAiAErUIAIARnIgRB0QBqENOBgIAAQYn/ACAEayEEIAIpAwhCgICAgICAwACFIQcgAikDACEICyAAIAg3AwAgACAErUIwhiADQR92rUI/hoQgB4Q3AwggAkEQaiSAgICAAAuhAQMBfwJ+AX8jgICAgABBEGsiAiSAgICAAAJAAkAgAQ0AQgAhA0IAIQQMAQsgAiABIAFBH3UiBXMgBWsiBa1CACAFZyIFQdEAahDTgYCAACACKQMIQoCAgICAgMAAhUGegAEgBWutQjCGfEKAgICAgICAgIB/QgAgAUEASBuEIQQgAikDACEDCyAAIAM3AwAgACAENwMIIAJBEGokgICAgAALgQECAX8CfiOAgICAAEEQayICJICAgIAAAkACQCABDQBCACEDQgAhBAwBCyACIAGtQgBB8AAgAWciAUEfc2sQ04GAgAAgAikDCEKAgICAgIDAAIVBnoABIAFrrUIwhnwhBCACKQMAIQMLIAAgAzcDACAAIAQ3AwggAkEQaiSAgICAAAsEAEEACwQAQQALUwEBfgJAAkAgA0HAAHFFDQAgAiADQUBqrYghAUIAIQIMAQsgA0UNACACQcAAIANrrYYgASADrSIEiIQhASACIASIIQILIAAgATcDACAAIAI3AwgLpwsGAX8EfgN/AX4Bfwp+I4CAgIAAQeAAayIFJICAgIAAIARC////////P4MhBiAEIAKFQoCAgICAgICAgH+DIQcgAkL///////8/gyIIQiCIIQkgBEIwiKdB//8BcSEKAkACQAJAIAJCMIinQf//AXEiC0GBgH5qQYKAfkkNAEEAIQwgCkGBgH5qQYGAfksNAQsCQCABUCACQv///////////wCDIg1CgICAgICAwP//AFQgDUKAgICAgIDA//8AURsNACACQoCAgICAgCCEIQcMAgsCQCADUCAEQv///////////wCDIgJCgICAgICAwP//AFQgAkKAgICAgIDA//8AURsNACAEQoCAgICAgCCEIQcgAyEBDAILAkAgASANQoCAgICAgMD//wCFhEIAUg0AAkAgAyAChFBFDQBCgICAgICA4P//ACEHQgAhAQwDCyAHQoCAgICAgMD//wCEIQdCACEBDAILAkAgAyACQoCAgICAgMD//wCFhEIAUg0AIAEgDYQhAkIAIQECQCACUEUNAEKAgICAgIDg//8AIQcMAwsgB0KAgICAgIDA//8AhCEHDAILAkAgASANhEIAUg0AQgAhAQwCCwJAIAMgAoRCAFINAEIAIQEMAgtBACEMAkAgDUL///////8/Vg0AIAVB0ABqIAEgCCABIAggCFAiDBt5QsAAQgAgDBt8pyIMQXFqENOBgIAAQRAgDGshDCAFKQNYIghCIIghCSAFKQNQIQELIAJC////////P1YNACAFQcAAaiADIAYgAyAGIAZQIg4beULAAEIAIA4bfKciDkFxahDTgYCAACAMIA5rQRBqIQwgBSkDSCEGIAUpA0AhAwsgA0IPhiINQoCA/v8PgyICIAFCIIgiBH4iDyANQiCIIg0gAUL/////D4MiAX58IhBCIIYiESACIAF+fCISIBFUrSACIAhC/////w+DIgh+IhMgDSAEfnwiESADQjGIIAZCD4YiFIRC/////w+DIgMgAX58IhUgEEIgiCAQIA9UrUIghoR8IhAgAiAJQoCABIQiBn4iFiANIAh+fCIJIBRCIIhCgICAgAiEIgIgAX58Ig8gAyAEfnwiFEIghnwiF3whASALIApqIAxqQYGAf2ohCgJAAkAgAiAEfiIYIA0gBn58IgQgGFStIAQgAyAIfnwiDSAEVK18IAIgBn58IA0gESATVK0gFSARVK18fCIEIA1UrXwgAyAGfiIDIAIgCH58IgIgA1StQiCGIAJCIIiEfCAEIAJCIIZ8IgIgBFStfCACIBRCIIggCSAWVK0gDyAJVK18IBQgD1StfEIghoR8IgQgAlStfCAEIBAgFVStIBcgEFStfHwiAiAEVK18IgRCgICAgICAwACDUA0AIApBAWohCgwBCyASQj+IIQMgBEIBhiACQj+IhCEEIAJCAYYgAUI/iIQhAiASQgGGIRIgAyABQgGGhCEBCwJAIApB//8BSA0AIAdCgICAgICAwP//AIQhB0IAIQEMAQsCQAJAIApBAEoNAAJAQQEgCmsiC0H/AEsNACAFQTBqIBIgASAKQf8AaiIKENOBgIAAIAVBIGogAiAEIAoQ04GAgAAgBUEQaiASIAEgCxDjgYCAACAFIAIgBCALEOOBgIAAIAUpAyAgBSkDEIQgBSkDMCAFKQM4hEIAUq2EIRIgBSkDKCAFKQMYhCEBIAUpAwghBCAFKQMAIQIMAgtCACEBDAILIAqtQjCGIARC////////P4OEIQQLIAQgB4QhBwJAIBJQIAFCf1UgAUKAgICAgICAgIB/URsNACAHIAJCAXwiAVCtfCEHDAELAkAgEiABQoCAgICAgICAgH+FhEIAUQ0AIAIhAQwBCyAHIAIgAkIBg3wiASACVK18IQcLIAAgATcDACAAIAc3AwggBUHgAGokgICAgAALdQEBfiAAIAQgAX4gAiADfnwgA0IgiCICIAFCIIgiBH58IANC/////w+DIgMgAUL/////D4MiAX4iBUIgiCADIAR+fCIDQiCIfCADQv////8PgyACIAF+fCIBQiCIfDcDCCAAIAFCIIYgBUL/////D4OENwMACyAAQYCAhIAAJIOAgIAAQYCAgIAAQQ9qQXBxJIKAgIAACw8AI4CAgIAAI4KAgIAAawsIACODgICAAAsIACOCgICAAAtUAQF/I4CAgIAAQRBrIgUkgICAgAAgBSABIAIgAyAEQoCAgICAgICAgH+FENKBgIAAIAUpAwAhBCAAIAUpAwg3AwggACAENwMAIAVBEGokgICAgAALmwQDAX8CfgR/I4CAgIAAQSBrIgIkgICAgAAgAUL///////8/gyEDAkACQCABQjCIQv//AYMiBKciBUH/h39qQf0PSw0AIABCPIggA0IEhoQhAyAFQYCIf2qtIQQCQAJAIABC//////////8PgyIAQoGAgICAgICACFQNACADQgF8IQMMAQsgAEKAgICAgICAgAhSDQAgA0IBgyADfCEDC0IAIAMgA0L/////////B1YiBRshACAFrSAEfCEDDAELAkAgACADhFANACAEQv//AVINACAAQjyIIANCBIaEQoCAgICAgIAEhCEAQv8PIQMMAQsCQCAFQf6HAU0NAEL/DyEDQgAhAAwBCwJAQYD4AEGB+AAgBFAiBhsiByAFayIIQfAATA0AQgAhAEIAIQMMAQsgAkEQaiAAIAMgA0KAgICAgIDAAIQgBhsiA0GAASAIaxDTgYCAACACIAAgAyAIEOOBgIAAIAIpAwAiA0I8iCACKQMIQgSGhCEAAkACQCADQv//////////D4MgByAFRyACKQMQIAIpAxiEQgBSca2EIgNCgYCAgICAgIAIVA0AIABCAXwhAAwBCyADQoCAgICAgICACFINACAAQgGDIAB8IQALIABCgICAgICAgAiFIAAgAEL/////////B1YiBRshACAFrSEDCyACQSBqJICAgIAAIANCNIYgAUKAgICAgICAgIB/g4QgAIS/CwoAIAAkgICAgAALGgECfyOAgICAACAAa0FwcSIBJICAgIAAIAELCAAjgICAgAALHgBBACAAIABBmQFLG0EBdC8B8O6EgABB8N+EgABqCwwAIAAgABDvgYCAAAsL1XICAEGAgAQLpHFpbmZpbml0eQBvdXQgb2YgbWVtb3J5AC0rICAgMFgweAAtMFgrMFggMFgtMHgrMHggMHgAbnVsbCBpbnB1dABpbXBsYXVzaWJsZSBlbGVtZW50IGNvdW50AGJhZCBwYWlyL3F1YWRydXBsZXQgY291bnQAbmVnYXRpdmUgUksgb3JkZXIgY291bnQAYmFkIGV4Y2Vzcy10ZXJtIGNvdW50AGJhZCBHaWJicy10ZXJtIGNvdW50AG5lZ2F0aXZlIGFkZGl0aW9uYWwtdGVybSBjb3VudABpbXBsYXVzaWJsZSBzb2x1dGlvbi1waGFzZSBjb3VudABzdWJsYXR0aWNlIHdpdGggbm8gY29uc3RpdHVlbnRzAGVuZG1lbWJlciB3aXRoIG5vIGludGVydmFscwB0b28gbWFueSBzdWJsYXR0aWNlcwBTVUJMIHBoYXNlIHdpdGggbm8gc3VibGF0dGljZXMAY2Fubm90IG9wZW4gJXMAbGluZSAlZDogJXMAZXZlcnkgc3VibGF0dGljZSBtdXN0IGFwcGVhciBvbmNlIGluIGFuIGV4Y2VzcyBwYXJhbWV0ZXIAZXhwZWN0ZWQgYW4gaW50ZWdlcgBleHBlY3RlZCBhIG51bWJlcgBuYW4AcGFpciBjb3VudCBkb2VzIG5vdCBlcXVhbCBuX2NhdCAqIG5fYW4AaW5mAGJhZCBzdWJsYXR0aWNlIHNpemUAdW5zdXBwb3J0ZWQgZXhjZXNzIG1peGluZyB0eXBlIGluIFNVQkwgcGhhc2UAdW5leHBlY3RlZCBlbmQgb2YgZmlsZQBleGNlc3MgY29uc3RpdHVlbnQgaW5kZXggb3V0IG9mIHJhbmdlAGV4Y2VzcyBwYXJhbWV0ZXIgd2l0aCBubyBtaXhpbmcgc3VibGF0dGljZQBjb25zdGFudCBtb2xhci12b2x1bWUgb3B0aW9ucyBhcmUgbm90IHN1cHBvcnRlZABQLVQgbW9sYXItdm9sdW1lIG9wdGlvbnMgYXJlIG5vdCBzdXBwb3J0ZWQAbm9uLXplcm8gcHJlLXR5cGUgZmxvYXRzIG9uIHNwZWNpZXMgbGluZSBub3Qgc3VwcG9ydGVkAG1vcmUgdGhhbiBiaW5hcnkgbWl4aW5nIG9uIG9uZSBzdWJsYXR0aWNlIG5vdCBzdXBwb3J0ZWQAcmVjaXByb2NhbCBleGNlc3MgKHR3byBtaXhpbmcgc3VibGF0dGljZXMpIG5vdCBzdXBwb3J0ZWQAb25seSBHaWJicy1lbmVyZ3kgZGF0YSBvcHRpb25zICgxLTYpIGFyZSBzdXBwb3J0ZWQAdGVsbCBmYWlsZWQAc2VlayBmYWlsZWQAcmIAcndhAFNVQlEATkFOAFNVQkxNAFNVQkwAU1VCRwBJTkYAVkEALgAobnVsbCkAcGhhc2UgdHlwZSAlcyBpcyBub3Qgc3VwcG9ydGVkIChvbmx5IFNVQlEvU1VCRy9TVUJMKQAjAAAAAAA4+v5CLuY/MGfHk1fzLj0BAAAAAADgv1swUVVVVdU/kEXr////z78RAfEks5nJP5/IBuV1VcW/AAAAAAAA4L93VVVVVVXVP8v9/////8+/DN2VmZmZyT+nRWdVVVXFvzDeRKMkScI/ZT1CpP//v7/K1ioohHG8P/9osEPrmbm/hdCv94KBtz/NRdF1E1K1v5/e4MPwNPc/AJDmeX/M178f6SxqeBP3PwAADcLub9e/oLX6CGDy9j8A4FET4xPXv32MEx+m0fY/AHgoOFu41r/RtMULSbH2PwB4gJBVXda/ugwvM0eR9j8AABh20ALWvyNCIhifcfY/AJCQhsqo1b/ZHqWZT1L2PwBQA1ZDT9W/xCSPqlYz9j8AQGvDN/bUvxTcnWuzFPY/AFCo/aed1L9MXMZSZPb1PwCoiTmSRdS/TyyRtWfY9T8AuLA59O3Tv96QW8u8uvU/AHCPRM6W0794GtnyYZ31PwCgvRceQNO/h1ZGElaA9T8AgEbv4unSv9Nr586XY/U/AOAwOBuU0r+Tf6fiJUf1PwCI2ozFPtK/g0UGQv8q9T8AkCcp4enRv9+9stsiD/U/APhIK22V0b/X3jRHj/P0PwD4uZpnQdG/QCjez0PY9D8AmO+U0O3Qv8ijeMA+vfQ/ABDbGKWa0L+KJeDDf6L0PwC4Y1LmR9C/NITUJAWI9D8A8IZFIuvPvwstGRvObfQ/ALAXdUpHz79UGDnT2VP0PwAwED1EpM6/WoS0RCc69D8AsOlEDQLOv/v4FUG1IPQ/APB3KaJgzb+x9D7aggf0PwCQlQQBwMy/j/5XXY/u8z8AEIlWKSDMv+lMC6DZ1fM/ABCBjReBy78rwRDAYL3zPwDQ08zJ4sq/uNp1KySl8z8AkBIuQEXKvwLQn80ijfM/APAdaHeoyb8ceoTFW3XzPwAwSGltDMm/4jatSc5d8z8AwEWmIHHIv0DUTZh5RvM/ADAUtI/Wx78ky//OXC/zPwBwYjy4PMe/SQ2hdXcY8z8AYDebmqPGv5A5PjfIAfM/AKC3VDELxr9B+JW7TuvyPwAwJHZ9c8W/0akZAgrV8j8AMMKPe9zEvyr9t6j5vvI/AADSUSxGxL+rGwx6HKnyPwAAg7yKsMO/MLUUYHKT8j8AAElrmRvDv/WhV1f6ffI/AECkkFSHwr+/Ox2bs2jyPwCgefi588G/vfWPg51T8j8AoCwlyGDBvzsIyaq3PvI/ACD3V3/OwL+2QKkrASryPwCg/kncPMC/MkHMlnkV8j8AgEu8vVe/v5v80h0gAfI/AEBAlgg3vr8LSE1J9OzxPwBA+T6YF72/aWWPUvXY8T8AoNhOZ/m7v3x+VxEjxfE/AGAvIHncur/pJst0fLHxPwCAKOfDwLm/thosDAGe8T8AwHKzRqa4v71wtnuwivE/AACsswGNt7+2vO8linfxPwAAOEXxdLa/2jFMNY1k8T8AgIdtDl61v91fJ5C5UfE/AOCh3lxItL9M0jKkDj/xPwCgak3ZM7O/2vkQcoss8T8AYMX4eSCyvzG17CgwGvE/ACBimEYOsb+vNITa+wfxPwAA0mps+q+/s2tOD+718D8AQHdKjdqtv86fKl0G5PA/AACF5Oy8q78hpSxjRNLwPwDAEkCJoam/GpjifKfA8D8AwAIzWIinv9E2xoMvr/A/AIDWZ15xpb85E6CY253wPwCAZUmKXKO/3+dSr6uM8D8AQBVk40mhv/soTi+fe/A/AIDrgsBynr8ZjzWMtWrwPwCAUlLxVZq/LPnspe5Z8D8AgIHPYj2Wv5As0c1JSfA/AACqjPsokr+prfDGxjjwPwAA+SB7MYy/qTJ5E2Uo8D8AAKpdNRmEv0hz6ickGPA/AADswgMSeL+VsRQGBAjwPwAAJHkJBGC/Gvom9x/g7z8AAJCE8+9vP3TqYcIcoe8/AAA9NUHchz8umYGwEGPvPwCAwsSjzpM/za3uPPYl7z8AAIkUwZ+bP+cTkQPI6e4/AAARztiwoT+rsct4gK7uPwDAAdBbiqU/mwydohp07j8AgNhAg1ypP7WZCoOROu4/AIBX72onrT9WmmAJ4AHuPwDAmOWYdbA/mLt35QHK7T8AIA3j9VOyPwORfAvyku0/AAA4i90utD/OXPtmrFztPwDAV4dZBrY/nd5eqiwn7T8AAGo1dtq3P80saz5u8uw/AGAcTkOruT8Ceaeibb7sPwBgDbvHeLs/bQg3bSaL7D8AIOcyE0O9PwRYXb2UWOw/AGDecTEKvz+Mn7sztSbsPwBAkSsVZ8A/P+fs7oP16z8AsJKChUfBP8GW23X9xOs/ADDKzW4mwj8oSoYMHpXrPwBQxabXA8M/LD7vxeJl6z8AEDM8w9/DP4uIyWdIN+s/AIB6aza6xD9KMB0hSwnrPwDw0Sg5k8U/fu/yhejb6j8A8BgkzWrGP6I9YDEdr+o/AJBm7PhAxz+nWNM/5oLqPwDwGvXAFcg/i3MJ70BX6j8AgPZUKenIPydLq5AqLOo/AED4Aja7yT/R8pMToAHqPwAALBzti8o/GzzbJJ/X6T8A0AFcUVvLP5CxxwUlruk/AMC8zGcpzD8vzpfyLoXpPwBgSNU19sw/dUuk7rpc6T8AwEY0vcHNPzhI553GNOk/AODPuAGMzj/mUmcvTw3pPwCQF8AJVc8/ndf/jlLm6D8AuB8SbA7QP3wAzJ/Ov+g/ANCTDrhx0D8Ow77awJnoPwBwhp5r1NA/+xcjqid06D8A0EszhzbRPwias6wAT+g/AEgjZw2Y0T9VPmXoSSroPwCAzOD/+NE/YAL0lQEG6D8AaGPXX1nSPymj4GMl4uc/AKgUCTC50j+ttdx3s77nPwBgQxByGNM/wiWXZ6qb5z8AGOxtJnfTP1cGF/IHeec/ADCv+0/V0z8ME9bbylbnPwDgL+PuMtQ/a7ZPAQAQ5j88W0KRbAJ+PJW0TQMAMOY/QV0ASOq/jTx41JQNAFDmP7el1oanf448rW9OBwBw5j9MJVRr6vxhPK4P3/7/j+Y//Q5ZTCd+fLy8xWMHALDmPwHa3EhowYq89sFcHgDQ5j8Rk0mdHD+DPD72Bev/7+Y/Uy3iGgSAfryAl4YOABDnP1J5CXFm/3s8Euln/P8v5z8kh70m4gCMPGoRgd//T+c/0gHxbpECbryQnGcPAHDnP3ScVM1x/Ge8Nch++v+P5z+DBPWewb6BPObCIP7/r+c/ZWTMKRd+cLwAyT/t/8/nPxyLewhygIC8dhom6f/v5z+u+Z1tKMCNPOijnAQAEOg/M0zlUdJ/iTyPLJMXADDoP4HzMLbp/oq8nHMzBgBQ6D+8NWVrv7+JPMaJQiAAcOg/dXsR82W/i7wEefXr/4/oP1fLPaJuAIm83wS8IgCw6D8KS+A43wB9vIobDOX/z+g/BZ//RnEAiLxDjpH8/+/oPzhwetB7gYM8x1/6HgAQ6T8DtN92kT6JPLl7RhMAMOk/dgKYS06AfzxvB+7m/0/pPy5i/9nwfo+80RI83v9v6T+6OCaWqoJwvA2KRfT/j+k/76hkkRuAh7w+Lpjd/6/pPzeTWorgQIe8ZvtJ7f/P6T8A4JvBCM4/PFGc8SAA8Ok/CluIJ6o/irwGsEURABDqP1baWJlI/3Q8+va7BwAw6j8YbSuKq76MPHkdlxAAUOo/MHl43cr+iDxILvUdAHDqP9ur2D12QY+8UjNZHACQ6j8SdsKEAr+OvEs+TyoAsOo/Xz//PAT9abzRHq7X/8/qP7RwkBLnPoK8eARR7v/v6j+j3g7gPgZqPFsNZdv/D+s/uQofOMgGWjxXyqr+/y/rPx08I3QeAXm83LqV2f9P6z+fKoZoEP95vJxlniQAcOs/Pk+G0EX/ijxAFof5/4/rP/nDwpZ3/nw8T8sE0v+v6z/EK/LuJ/9jvEVcQdL/z+s/Ieo77rf/bLzfCWP4/+/rP1wLLpcDQYG8U3a14f8P7D8ZareUZMGLPONX+vH/L+w/7cYwje/+ZLwk5L/c/0/sP3VH7LxoP4S897lU7f9v7D/s4FPwo36EPNWPmev/j+w/8ZL5jQaDczyaISUhALDsPwQOGGSO/Wi8nEaU3f/P7D9y6sccvn6OPHbE/er/7+w//oifrTm+jjwr+JoWABDtP3FauaiRfXU8HfcPDQAw7T/ax3BpkMGJPMQPeer/T+0/DP5YxTcOWLzlh9wuAHDtP0QPwU3WgH+8qoLcIQCQ7T9cXP2Uj3x0vIMCa9j/r+0/fmEhxR1/jDw5R2wpANDtP1Ox/7KeAYg89ZBE5f/v7T+JzFLG0gBuPJT2q83/D+4/0mktIECDf7zdyFLb/y/uP2QIG8rBAHs87xZC8v9P7j9Rq5SwqP9yPBFeiuj/b+4/Wb7vsXP2V7wN/54RAJDuPwHIC16NgIS8RBel3/+v7j+1IEPVBgB4PKF/EhoA0O4/klxWYPgCULzEvLoHAPDuPxHmNV1EQIW8Ao169f8P7z8Fke85MftPvMeK5R4AMO8/VRFz8qyBijyUNIL1/0/vP0PH19RBP4o8a0yp/P9v7z91eJgc9AJivEHE+eH/j+8/S+d39NF9dzx+4+DS/6/vPzGjfJoZAW+8nuR3HADQ7z+xrM5L7oFxPDHD4Pf/7+8/WodwATcFbrxuYGX0/w/wP9oKHEmtfoq8WHqG8/8v8D/gsvzDaX+XvBcN/P3/T/A/W5TLNP6/lzyCTc0DAHDwP8tW5MCDAII86Mvy+f+P8D8adTe+3/9tvGXaDAEAsPA/6ybmrn8/kbw406QBANDwP/efSHn6fYA8/f3a+v/v8D/Aa9ZwBQR3vJb9ugsAEPE/YgtthNSAjjxd9OX6/y/xP+82/WT6v5082ZrVDQBQ8T+uUBJwdwCaPJpVIQ8AcPE/7t7j4vn9jTwmVCf8/4/xP3NyO9wwAJE8WTw9EgCw8T+IAQOAeX+ZPLeeKfj/z/E/Z4yfqzL5ZbwA1Ir0/+/xP+tbp52/f5M8pIaLDAAQ8j8iW/2Ra4CfPANDhQMAMPI/M7+f68L/kzyE9rz//0/yP3IuLn7nAXY82SEp9f9v8j9hDH92u/x/PDw6kxQAkPI/K0ECPMoCcrwTY1UUALDyPwIf8jOCgJK8O1L+6//P8j/y3E84fv+IvJatuAsA8PI/xUEwUFH/hbyv4nr7/w/zP50oXohxAIG8f1+s/v8v8z8Vt7c/Xf+RvFZnpgwAUPM/vYKLIoJ/lTwh9/sRAHDzP8zVDcS6AIA8uS9Z+f+P8z9Rp7ItnT+UvELS3QQAsPM/4Th2cGt/hTxXybL1/8/zPzESvxA6Ano8GLSw6v/v8z+wUrFmbX+YPPSvMhUAEPQ/JIUZXzf4Zzwpi0cXADD0P0NR3HLmAYM8Y7SV5/9P9D9aibK4af+JPOB1BOj/b/Q/VPLCm7HAlbznwW/v/4/0P3IqOvIJQJs8BKe+5f+v9D9FfQ2/t/+UvN4nEBcA0PQ/PWrccWTAmbziPvAPAPD0PxxThQuJf5c80UvcEgAQ9T82pGZxZQRgPHonBRYAMPU/CTIjzs6/lrxMcNvs/0/1P9ehBQVyAom8qVRf7/9v9T8SZMkO5r+bPBIQ5hcAkPU/kO+vgcV+iDySPskDALD1P8AMvwoIQZ+8vBlJHQDQ9T8pRyX7KoGYvIl6uOf/7/U/BGntgLd+lLz+gitlRxVnQAAAAAAAADhDAAD6/kIudr86O568mvcMvb39/////98/PFRVVVVVxT+RKxfPVVWlPxfQpGcREYE/AAAAAAAAyELvOfr+Qi7mPyTEgv+9v84/tfQM1whrrD/MUEbSq7KDP4Q6Tpvg11U/AAAAAAAAAAAAAAAAAADwP26/iBpPO5s8NTP7qT327z9d3NicE2BxvGGAdz6a7O8/0WaHEHpekLyFf27oFePvPxP2ZzVS0ow8dIUV07DZ7z/6jvkjgM6LvN723Slr0O8/YcjmYU73YDzIm3UYRcfvP5nTM1vko5A8g/PGyj6+7z9te4NdppqXPA+J+WxYte8//O/9khq1jjz3R3IrkqzvP9GcL3A9vj48otHTMuyj7z8LbpCJNANqvBvT/q9mm+8/Dr0vKlJWlbxRWxLQAZPvP1XqTozvgFC8zDFswL2K7z8W9NW5I8mRvOAtqa6agu8/r1Vc6ePTgDxRjqXImHrvP0iTpeoVG4C8e1F9PLhy7z89Mt5V8B+PvOqNjDj5au8/v1MTP4yJizx1y2/rW2PvPybrEXac2Za81FwEhOBb7z9gLzo+9+yaPKq5aDGHVO8/nTiGy4Lnj7wd2fwiUE3vP43DpkRBb4o81oxiiDtG7z99BOSwBXqAPJbcfZFJP+8/lKio4/2Oljw4YnVuejjvP31IdPIYXoc8P6ayT84x7z/y5x+YK0eAPN184mVFK+8/XghxP3u4lryBY/Xh3yTvPzGrCW3h94I84d4f9Z0e7z/6v28amyE9vJDZ2tB/GO8/tAoMcoI3izwLA+SmhRLvP4/LzomSFG48Vi8+qa8M7z+2q7BNdU2DPBW3MQr+Bu8/THSs4gFChjwx2Ez8cAHvP0r401053Y88/xZksgj87j8EW447gKOGvPGfkl/F9u4/aFBLzO1KkrzLqTo3p/HuP44tURv4B5m8ZtgFba7s7j/SNpQ+6NFxvPef5TTb5+4/FRvOsxkZmbzlqBPDLePuP21MKqdIn4U8IjQSTKbe7j+KaSh6YBKTvByArARF2u4/W4kXSI+nWLwqLvchCtbuPxuaSWebLHy8l6hQ2fXR7j8RrMJg7WNDPC2JYWAIzu4/72QGOwlmljxXAB3tQcruP3kDodrhzG480DzBtaLG7j8wEg8/jv+TPN7T1/Aqw+4/sK96u86QdjwnKjbV2r/uP3fgVOu9HZM8Dd39mbK87j+Oo3EANJSPvKcsnXayue4/SaOT3Mzeh7xCZs+i2rbuP184D73G3ni8gk+dViu07j/2XHvsRhKGvA+SXcqkse4/jtf9GAU1kzzaJ7U2R6/uPwWbii+3mHs8/ceX1BKt7j8JVBzi4WOQPClUSN0Hq+4/6sYZUIXHNDy3RlmKJqnuPzXAZCvmMpQ8SCGtFW+n7j+fdplhSuSMvAncdrnhpe4/qE3vO8UzjLyFVTqwfqTuP67pK4l4U4S8IMPMNEaj7j9YWFZ43c6TvCUiVYI4ou4/ZBl+gKoQVzxzqUzUVaHuPygiXr/vs5O8zTt/Zp6g7j+CuTSHrRJqvL/aC3USoO4/7qltuO9nY7wvGmU8sp/uP1GI4FQ93IC8hJRR+X2f7j/PPlp+ZB94vHRf7Oh1n+4/sH2LwEruhrx0gaVImp/uP4rmVR4yGYa8yWdCVuuf7j/T1Aley5yQPD9d3k9poO4/HaVNudwye7yHAetzFKHuP2vAZ1T97JQ8MsEwAe2h7j9VbNar4etlPGJOzzbzou4/Qs+zL8WhiLwSGj5UJ6TuPzQ3O/G2aZO8E85MmYml7j8e/xk6hF6AvK3HI0Yap+4/bldy2FDUlLztkkSb2ajuPwCKDltnrZA8mWaK2ceq7j+06vDBL7eNPNugKkLlrO4//+fFnGC2ZbyMRLUWMq/uP0Rf81mD9ns8NncVma6x7j+DPR6nHwmTvMb/kQtbtO4/KR5si7ipXbzlxc2wN7fuP1m5kHz5I2y8D1LIy0S67j+q+fQiQ0OSvFBO3p+Cve4/S45m12zKhby6B8pw8cDuPyfOkSv8r3E8kPCjgpHE7j+7cwrhNdJtPCMj4xljyO4/YyJiIgTFh7xl5V17ZszuP9Ux4uOGHIs8My1K7JvQ7j8Vu7zT0buRvF0lPrID1e4/0jHunDHMkDxYszATntnuP7Nac26EaYQ8v/15VWve7j+0nY6Xzd+CvHrz079r4+4/hzPLkncajDyt01qZn+juP/rZ0UqPe5C8ZraNKQfu7j+6rtxW2cNVvPsVT7ii8+4/QPamPQ6kkLw6WeWNcvnuPzSTrTj01mi8R1778nb/7j81ilhr4u6RvEoGoTCwBe8/zd1fCtf/dDzSwUuQHgzvP6yYkvr7vZG8CR7XW8IS7z+zDK8wrm5zPJxShd2bGe8/lP2fXDLjjjx60P9fqyDvP6xZCdGP4IQ8S9FXLvEn7z9nGk44r81jPLXnBpRtL+8/aBmSbCxrZzxpkO/cIDfvP9K1zIMYioC8+sNdVQs/7z9v+v8/Xa2PvHyJB0otR+8/Sal1OK4NkLzyiQ0Ih0/vP6cHPaaFo3Q8h6T73BhY7z8PIkAgnpGCvJiDyRbjYO8/rJLB1VBajjyFMtsD5mnvP0trAaxZOoQ8YLQB8yFz7z8fPrQHIdWCvF+bezOXfO8/yQ1HO7kqibwpofUURobvP9OIOmAEtnQ89j+L5y6Q7z9xcp1R7MWDPINMx/tRmu8/8JHTjxL3j7zakKSir6TvP310I+KYro288WeOLUiv7z8IIKpBvMOOPCdaYe4buu8/Muupw5QrhDyXums3K8XvP+6F0TGpZIo8QEVuW3bQ7z/t4zvkujeOvBS+nK392+8/nc2RTTuJdzzYkJ6BwefvP4nMYEHBBVM88XGPK8Lz7z8AOPr+Qi7mPzBnx5NX8y49AAAAAAAA4L9gVVVVVVXlvwYAAAAAAOA/TlVZmZmZ6T96pClVVVXlv+lFSJtbSfK/wz8miysA8D8AAAAAAKD2PwAAAAAAAAAAAMi58oIs1r+AVjcoJLT6PAAAAAAAgPY/AAAAAAAAAAAACFi/vdHVvyD34NgIpRy9AAAAAABg9j8AAAAAAAAAAABYRRd3dtW/bVC21aRiI70AAAAAAED2PwAAAAAAAAAAAPgth60a1b/VZ7Ce5ITmvAAAAAAAIPY/AAAAAAAAAAAAeHeVX77Uv+A+KZNpGwS9AAAAAAAA9j8AAAAAAAAAAABgHMKLYdS/zIRMSC/YEz0AAAAAAOD1PwAAAAAAAAAAAKiGhjAE1L86C4Lt80LcPAAAAAAAwPU/AAAAAAAAAAAASGlVTKbTv2CUUYbGsSA9AAAAAACg9T8AAAAAAAAAAACAmJrdR9O/koDF1E1ZJT0AAAAAAID1PwAAAAAAAAAAACDhuuLo0r/YK7eZHnsmPQAAAAAAYPU/AAAAAAAAAAAAiN4TWonSvz+wz7YUyhU9AAAAAABg9T8AAAAAAAAAAACI3hNaidK/P7DPthTKFT0AAAAAAED1PwAAAAAAAAAAAHjP+0Ep0r922lMoJFoWvQAAAAAAIPU/AAAAAAAAAAAAmGnBmMjRvwRU52i8rx+9AAAAAAAA9T8AAAAAAAAAAACoq6tcZ9G/8KiCM8YfHz0AAAAAAOD0PwAAAAAAAAAAAEiu+YsF0b9mWgX9xKgmvQAAAAAAwPQ/AAAAAAAAAAAAkHPiJKPQvw4D9H7uawy9AAAAAACg9D8AAAAAAAAAAADQtJQlQNC/fy30nrg28LwAAAAAAKD0PwAAAAAAAAAAANC0lCVA0L9/LfSeuDbwvAAAAAAAgPQ/AAAAAAAAAAAAQF5tGLnPv4c8masqVw09AAAAAABg9D8AAAAAAAAAAABg3Mut8M6/JK+GnLcmKz0AAAAAAED0PwAAAAAAAAAAAPAqbgcnzr8Q/z9UTy8XvQAAAAAAIPQ/AAAAAAAAAAAAwE9rIVzNvxtoyruRuiE9AAAAAAAA9D8AAAAAAAAAAACgmsf3j8y/NISfaE95Jz0AAAAAAAD0PwAAAAAAAAAAAKCax/ePzL80hJ9oT3knPQAAAAAA4PM/AAAAAAAAAAAAkC10hsLLv4+3izGwThk9AAAAAADA8z8AAAAAAAAAAADAgE7J88q/ZpDNP2NOujwAAAAAAKDzPwAAAAAAAAAAALDiH7wjyr/qwUbcZIwlvQAAAAAAoPM/AAAAAAAAAAAAsOIfvCPKv+rBRtxkjCW9AAAAAACA8z8AAAAAAAAAAABQ9JxaUsm/49TBBNnRKr0AAAAAAGDzPwAAAAAAAAAAANAgZaB/yL8J+tt/v70rPQAAAAAAQPM/AAAAAAAAAAAA4BACiavHv1hKU3KQ2ys9AAAAAABA8z8AAAAAAAAAAADgEAKJq8e/WEpTcpDbKz0AAAAAACDzPwAAAAAAAAAAANAZ5w/Wxr9m4rKjauQQvQAAAAAAAPM/AAAAAAAAAAAAkKdwMP/FvzlQEJ9Dnh69AAAAAAAA8z8AAAAAAAAAAACQp3Aw/8W/OVAQn0OeHr0AAAAAAODyPwAAAAAAAAAAALCh4+Umxb+PWweQi94gvQAAAAAAwPI/AAAAAAAAAAAAgMtsK03Evzx4NWHBDBc9AAAAAADA8j8AAAAAAAAAAACAy2wrTcS/PHg1YcEMFz0AAAAAAKDyPwAAAAAAAAAAAJAeIPxxw786VCdNhnjxPAAAAAAAgPI/AAAAAAAAAAAA8B/4UpXCvwjEcRcwjSS9AAAAAABg8j8AAAAAAAAAAABgL9Uqt8G/lqMRGKSALr0AAAAAAGDyPwAAAAAAAAAAAGAv1Sq3wb+WoxEYpIAuvQAAAAAAQPI/AAAAAAAAAAAAkNB8ftfAv/Rb6IiWaQo9AAAAAABA8j8AAAAAAAAAAACQ0Hx+18C/9FvoiJZpCj0AAAAAACDyPwAAAAAAAAAAAODbMZHsv7/yM6NcVHUlvQAAAAAAAPI/AAAAAAAAAAAAACtuBye+vzwA8CosNCo9AAAAAAAA8j8AAAAAAAAAAAAAK24HJ76/PADwKiw0Kj0AAAAAAODxPwAAAAAAAAAAAMBbj1RevL8Gvl9YVwwdvQAAAAAAwPE/AAAAAAAAAAAA4Eo6bZK6v8iqW+g1OSU9AAAAAADA8T8AAAAAAAAAAADgSjptkrq/yKpb6DU5JT0AAAAAAKDxPwAAAAAAAAAAAKAx1kXDuL9oVi9NKXwTPQAAAAAAoPE/AAAAAAAAAAAAoDHWRcO4v2hWL00pfBM9AAAAAACA8T8AAAAAAAAAAABg5YrS8La/2nMzyTeXJr0AAAAAAGDxPwAAAAAAAAAAACAGPwcbtb9XXsZhWwIfPQAAAAAAYPE/AAAAAAAAAAAAIAY/Bxu1v1dexmFbAh89AAAAAABA8T8AAAAAAAAAAADgG5bXQbO/3xP5zNpeLD0AAAAAAEDxPwAAAAAAAAAAAOAbltdBs7/fE/nM2l4sPQAAAAAAIPE/AAAAAAAAAAAAgKPuNmWxvwmjj3ZefBQ9AAAAAAAA8T8AAAAAAAAAAACAEcAwCq+/kY42g55ZLT0AAAAAAADxPwAAAAAAAAAAAIARwDAKr7+RjjaDnlktPQAAAAAA4PA/AAAAAAAAAAAAgBlx3UKrv0xw1uV6ghw9AAAAAADg8D8AAAAAAAAAAACAGXHdQqu/THDW5XqCHD0AAAAAAMDwPwAAAAAAAAAAAMAy9lh0p7/uofI0RvwsvQAAAAAAwPA/AAAAAAAAAAAAwDL2WHSnv+6h8jRG/Cy9AAAAAACg8D8AAAAAAAAAAADA/rmHnqO/qv4m9bcC9TwAAAAAAKDwPwAAAAAAAAAAAMD+uYeeo7+q/ib1twL1PAAAAAAAgPA/AAAAAAAAAAAAAHgOm4Kfv+QJfnwmgCm9AAAAAACA8D8AAAAAAAAAAAAAeA6bgp+/5Al+fCaAKb0AAAAAAGDwPwAAAAAAAAAAAIDVBxu5l785pvqTVI0ovQAAAAAAQPA/AAAAAAAAAAAAAPywqMCPv5ym0/Z8Ht+8AAAAAABA8D8AAAAAAAAAAAAA/LCowI+/nKbT9nwe37wAAAAAACDwPwAAAAAAAAAAAAAQayrgf7/kQNoNP+IZvQAAAAAAIPA/AAAAAAAAAAAAABBrKuB/v+RA2g0/4hm9AAAAAAAA8D8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADwPwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwO8/AAAAAAAAAAAAAIl1FRCAP+grnZlrxxC9AAAAAACA7z8AAAAAAAAAAACAk1hWIJA/0vfiBlvcI70AAAAAAEDvPwAAAAAAAAAAAADJKCVJmD80DFoyuqAqvQAAAAAAAO8/AAAAAAAAAAAAQOeJXUGgP1PX8VzAEQE9AAAAAADA7j8AAAAAAAAAAAAALtSuZqQ/KP29dXMWLL0AAAAAAIDuPwAAAAAAAAAAAMCfFKqUqD99JlrQlXkZvQAAAAAAQO4/AAAAAAAAAAAAwN3Nc8usPwco2EfyaBq9AAAAAAAg7j8AAAAAAAAAAADABsAx6q4/ezvJTz4RDr0AAAAAAODtPwAAAAAAAAAAAGBG0TuXsT+bng1WXTIlvQAAAAAAoO0/AAAAAAAAAAAA4NGn9b2zP9dO26VeyCw9AAAAAABg7T8AAAAAAAAAAACgl01a6bU/Hh1dPAZpLL0AAAAAAEDtPwAAAAAAAAAAAMDqCtMAtz8y7Z2pjR7sPAAAAAAAAO0/AAAAAAAAAAAAQFldXjO5P9pHvTpcESM9AAAAAADA7D8AAAAAAAAAAABgrY3Iars/5Wj3K4CQE70AAAAAAKDsPwAAAAAAAAAAAEC8AViIvD/TrFrG0UYmPQAAAAAAYOw/AAAAAAAAAAAAIAqDOce+P+BF5q9owC29AAAAAABA7D8AAAAAAAAAAADg2zmR6L8//QqhT9Y0Jb0AAAAAAADsPwAAAAAAAAAAAOAngo4XwT/yBy3OeO8hPQAAAAAA4Os/AAAAAAAAAAAA8CN+K6rBPzSZOESOpyw9AAAAAACg6z8AAAAAAAAAAACAhgxh0cI/obSBy2ydAz0AAAAAAIDrPwAAAAAAAAAAAJAVsPxlwz+JcksjqC/GPAAAAAAAQOs/AAAAAAAAAAAAsDODPZHEP3i2/VR5gyU9AAAAAAAg6z8AAAAAAAAAAACwoeTlJ8U/x31p5egzJj0AAAAAAODqPwAAAAAAAAAAABCMvk5Xxj94Ljwsi88ZPQAAAAAAwOo/AAAAAAAAAAAAcHWLEvDGP+EhnOWNESW9AAAAAACg6j8AAAAAAAAAAABQRIWNicc/BUORcBBmHL0AAAAAAGDqPwAAAAAAAAAAAAA566++yD/RLOmqVD0HvQAAAAAAQOo/AAAAAAAAAAAAAPfcWlrJP2//oFgo8gc9AAAAAAAA6j8AAAAAAAAAAADgijztk8o/aSFWUENyKL0AAAAAAODpPwAAAAAAAAAAANBbV9gxyz+q4axOjTUMvQAAAAAAwOk/AAAAAAAAAAAA4Ds4h9DLP7YSVFnESy29AAAAAACg6T8AAAAAAAAAAAAQ8Mb7b8w/0iuWxXLs8bwAAAAAAGDpPwAAAAAAAAAAAJDUsD2xzT81sBX3Kv8qvQAAAAAAQOk/AAAAAAAAAAAAEOf/DlPOPzD0QWAnEsI8AAAAAAAg6T8AAAAAAAAAAAAA3eSt9c4/EY67ZRUhyrwAAAAAAADpPwAAAAAAAAAAALCzbByZzz8w3wzK7MsbPQAAAAAAwOg/AAAAAAAAAAAAWE1gOHHQP5FO7RbbnPg8AAAAAACg6D8AAAAAAAAAAABgYWctxNA/6eo8FosYJz0AAAAAAIDoPwAAAAAAAAAAAOgngo4X0T8c8KVjDiEsvQAAAAAAYOg/AAAAAAAAAAAA+KzLXGvRP4EWpffNmis9AAAAAABA6D8AAAAAAAAAAABoWmOZv9E/t71HUe2mLD0AAAAAACDoPwAAAAAAAAAAALgObUUU0j/quka63ocKPQAAAAAA4Oc/AAAAAAAAAAAAkNx88L7SP/QEUEr6nCo9AAAAAADA5z8AAAAAAAAAAABg0+HxFNM/uDwh03riKL0AAAAAAKDnPwAAAAAAAAAAABC+dmdr0z/Id/GwzW4RPQAAAAAAgOc/AAAAAAAAAAAAMDN3UsLTP1y9BrZUOxg9AAAAAABg5z8AAAAAAAAAAADo1SO0GdQ/neCQ7DbkCD0AAAAAAEDnPwAAAAAAAAAAAMhxwo1x1D911mcJzicvvQAAAAAAIOc/AAAAAAAAAAAAMBee4MnUP6TYChuJIC69AAAAAAAA5z8AAAAAAAAAAACgOAeuItU/WcdkgXC+Lj0AAAAAAODmPwAAAAAAAAAAANDIU/d71T/vQF3u7a0fPQAAAAAAwOY/AAAAAAAAAAAAYFnfvdXVP9xlpAgqCwq9AAAAAAAAAADRdJ4AV529KoBwUg///z4nCgAAAGQAAADoAwAAECcAAKCGAQBAQg8AgJaYAADh9QUYAAAANQAAAHEAAABr////zvv//5K///8AAAAAAAAAABkACwAZGRkAAAAABQAAAAAAAAkAAAAACwAAAAAAAAAAGQAKChkZGQMKBwABAAkLGAAACQYLAAALAAYZAAAAGRkZAAAAAAAAAAAAAAAAAAAAAA4AAAAAAAAAABkACw0ZGRkADQAAAgAJDgAAAAkADgAADgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAATAAAAABMAAAAACQwAAAAAAAwAAAwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAADwAAAAQPAAAAAAkQAAAAAAAQAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABIAAAAAAAAAAAAAABEAAAAAEQAAAAAJEgAAAAAAEgAAEgAAGgAAABoaGgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAaAAAAGhoaAAAAAAAACQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFAAAAAAAAAAAAAAAFwAAAAAXAAAAAAkUAAAAAAAUAAAUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABYAAAAAAAAAAAAAABUAAAAAFQAAAAAJFgAAAAAAFgAAFgAAMDEyMzQ1Njc4OUFCQ0RFRk5vIGVycm9yIGluZm9ybWF0aW9uAElsbGVnYWwgYnl0ZSBzZXF1ZW5jZQBEb21haW4gZXJyb3IAUmVzdWx0IG5vdCByZXByZXNlbnRhYmxlAE5vdCBhIHR0eQBQZXJtaXNzaW9uIGRlbmllZABPcGVyYXRpb24gbm90IHBlcm1pdHRlZABObyBzdWNoIGZpbGUgb3IgZGlyZWN0b3J5AE5vIHN1Y2ggcHJvY2VzcwBGaWxlIGV4aXN0cwBWYWx1ZSB0b28gbGFyZ2UgZm9yIGRhdGEgdHlwZQBObyBzcGFjZSBsZWZ0IG9uIGRldmljZQBPdXQgb2YgbWVtb3J5AFJlc291cmNlIGJ1c3kASW50ZXJydXB0ZWQgc3lzdGVtIGNhbGwAUmVzb3VyY2UgdGVtcG9yYXJpbHkgdW5hdmFpbGFibGUASW52YWxpZCBzZWVrAENyb3NzLWRldmljZSBsaW5rAFJlYWQtb25seSBmaWxlIHN5c3RlbQBEaXJlY3Rvcnkgbm90IGVtcHR5AENvbm5lY3Rpb24gcmVzZXQgYnkgcGVlcgBPcGVyYXRpb24gdGltZWQgb3V0AENvbm5lY3Rpb24gcmVmdXNlZABIb3N0IGlzIGRvd24ASG9zdCBpcyB1bnJlYWNoYWJsZQBBZGRyZXNzIGluIHVzZQBCcm9rZW4gcGlwZQBJL08gZXJyb3IATm8gc3VjaCBkZXZpY2Ugb3IgYWRkcmVzcwBCbG9jayBkZXZpY2UgcmVxdWlyZWQATm8gc3VjaCBkZXZpY2UATm90IGEgZGlyZWN0b3J5AElzIGEgZGlyZWN0b3J5AFRleHQgZmlsZSBidXN5AEV4ZWMgZm9ybWF0IGVycm9yAEludmFsaWQgYXJndW1lbnQAQXJndW1lbnQgbGlzdCB0b28gbG9uZwBTeW1ib2xpYyBsaW5rIGxvb3AARmlsZW5hbWUgdG9vIGxvbmcAVG9vIG1hbnkgb3BlbiBmaWxlcyBpbiBzeXN0ZW0ATm8gZmlsZSBkZXNjcmlwdG9ycyBhdmFpbGFibGUAQmFkIGZpbGUgZGVzY3JpcHRvcgBObyBjaGlsZCBwcm9jZXNzAEJhZCBhZGRyZXNzAEZpbGUgdG9vIGxhcmdlAFRvbyBtYW55IGxpbmtzAE5vIGxvY2tzIGF2YWlsYWJsZQBSZXNvdXJjZSBkZWFkbG9jayB3b3VsZCBvY2N1cgBTdGF0ZSBub3QgcmVjb3ZlcmFibGUAUHJldmlvdXMgb3duZXIgZGllZABPcGVyYXRpb24gY2FuY2VsZWQARnVuY3Rpb24gbm90IGltcGxlbWVudGVkAE5vIG1lc3NhZ2Ugb2YgZGVzaXJlZCB0eXBlAElkZW50aWZpZXIgcmVtb3ZlZABEZXZpY2Ugbm90IGEgc3RyZWFtAE5vIGRhdGEgYXZhaWxhYmxlAERldmljZSB0aW1lb3V0AE91dCBvZiBzdHJlYW1zIHJlc291cmNlcwBMaW5rIGhhcyBiZWVuIHNldmVyZWQAUHJvdG9jb2wgZXJyb3IAQmFkIG1lc3NhZ2UARmlsZSBkZXNjcmlwdG9yIGluIGJhZCBzdGF0ZQBOb3QgYSBzb2NrZXQARGVzdGluYXRpb24gYWRkcmVzcyByZXF1aXJlZABNZXNzYWdlIHRvbyBsYXJnZQBQcm90b2NvbCB3cm9uZyB0eXBlIGZvciBzb2NrZXQAUHJvdG9jb2wgbm90IGF2YWlsYWJsZQBQcm90b2NvbCBub3Qgc3VwcG9ydGVkAFNvY2tldCB0eXBlIG5vdCBzdXBwb3J0ZWQATm90IHN1cHBvcnRlZABQcm90b2NvbCBmYW1pbHkgbm90IHN1cHBvcnRlZABBZGRyZXNzIGZhbWlseSBub3Qgc3VwcG9ydGVkIGJ5IHByb3RvY29sAEFkZHJlc3Mgbm90IGF2YWlsYWJsZQBOZXR3b3JrIGlzIGRvd24ATmV0d29yayB1bnJlYWNoYWJsZQBDb25uZWN0aW9uIHJlc2V0IGJ5IG5ldHdvcmsAQ29ubmVjdGlvbiBhYm9ydGVkAE5vIGJ1ZmZlciBzcGFjZSBhdmFpbGFibGUAU29ja2V0IGlzIGNvbm5lY3RlZABTb2NrZXQgbm90IGNvbm5lY3RlZABDYW5ub3Qgc2VuZCBhZnRlciBzb2NrZXQgc2h1dGRvd24AT3BlcmF0aW9uIGFscmVhZHkgaW4gcHJvZ3Jlc3MAT3BlcmF0aW9uIGluIHByb2dyZXNzAFN0YWxlIGZpbGUgaGFuZGxlAFJlbW90ZSBJL08gZXJyb3IAUXVvdGEgZXhjZWVkZWQATm8gbWVkaXVtIGZvdW5kAFdyb25nIG1lZGl1bSB0eXBlAE11bHRpaG9wIGF0dGVtcHRlZABSZXF1aXJlZCBrZXkgbm90IGF2YWlsYWJsZQBLZXkgaGFzIGV4cGlyZWQAS2V5IGhhcyBiZWVuIHJldm9rZWQAS2V5IHdhcyByZWplY3RlZCBieSBzZXJ2aWNlAAAAAAAAAAAApQJbAPABtQWMBSUBgwYdA5QE/wDHAzEDCwa8AY8BfwPKBCsA2gavAEIDTgPcAQ4EFQChBg0BlAILAjgGZAK8Av8CXQPnBAsHzwLLBe8F2wXhAh4GRQKFAIICbANvBPEA8wMYBdkA2gNMBlQCewGdA70EAABRABUCuwCzA20A/wGFBC8F+QQ4AGUBRgGfALcGqAFzAlMBAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIQQAAAAAAAAAAC8CAAAAAAAAAAAAAAAAAAAAAAAAAAA1BEcEVgQAAAAAAAAAAAAAAAAAAAAAoAQAAAAAAAAAAAAAAAAAAAAAAABGBWAFbgVhBgAAzwEAAAAAAAAAAMkG6Qb5Bh4HOQdJB14HAEGo8QQLoAEAIAAAAAAAAAUAAAAAAAAAAAAAAAkAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAcAAAAGAAAAJDsBAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAD//////////wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAALA4AQAgPQEAAJQBD3RhcmdldF9mZWF0dXJlcwgrC2J1bGstbWVtb3J5Kw9idWxrLW1lbW9yeS1vcHQrFmNhbGwtaW5kaXJlY3Qtb3ZlcmxvbmcrCm11bHRpdmFsdWUrD211dGFibGUtZ2xvYmFscysTbm9udHJhcHBpbmctZnB0b2ludCsPcmVmZXJlbmNlLXR5cGVzKwhzaWduLWV4dA==');
}

function getBinarySync(file) {
  if (ArrayBuffer.isView(file)) {
    return file;
  }
  if (file == wasmBinaryFile && wasmBinary) {
    return new Uint8Array(wasmBinary);
  }
  if (readBinary) {
    return readBinary(file);
  }
  throw 'both async and sync fetching of the wasm failed';
}

async function getWasmBinary(binaryFile) {

  // Otherwise, getBinarySync should be able to get it synchronously
  return getBinarySync(binaryFile);
}

async function instantiateArrayBuffer(binaryFile, imports) {
  try {
    var binary = await getWasmBinary(binaryFile);
    var instance = await WebAssembly.instantiate(binary, imports);
    return instance;
  } catch (reason) {
    err(`failed to asynchronously prepare wasm: ${reason}`);

    // Warn on some common problems.
    if (isFileURI(wasmBinaryFile)) {
      err(`warning: Loading from a file URI (${wasmBinaryFile}) is not supported in most browsers. See https://emscripten.org/docs/getting_started/FAQ.html#how-do-i-run-a-local-webserver-for-testing-why-does-my-program-stall-in-downloading-or-preparing`);
    }
    abort(reason);
  }
}

async function instantiateAsync(binary, binaryFile, imports) {
  return instantiateArrayBuffer(binaryFile, imports);
}

function getWasmImports() {
  // prepare imports
  return {
    'env': wasmImports,
    'wasi_snapshot_preview1': wasmImports,
  }
}

// Create the wasm instance.
// Receives the wasm imports, returns the exports.
async function createWasm() {
  // Load the wasm module and create an instance of using native support in the JS engine.
  // handle a generated wasm instance, receiving its exports and
  // performing other necessary setup
  /** @param {WebAssembly.Module=} module*/
  function receiveInstance(instance, module) {
    wasmExports = instance.exports;

    

    wasmMemory = wasmExports['memory'];
    
    assert(wasmMemory, 'memory not found in wasm exports');
    updateMemoryViews();

    wasmTable = wasmExports['__indirect_function_table'];
    
    assert(wasmTable, 'table not found in wasm exports');

    removeRunDependency('wasm-instantiate');
    return wasmExports;
  }
  // wait for the pthread pool (if any)
  addRunDependency('wasm-instantiate');

  // Prefer streaming instantiation if available.
  // Async compilation can be confusing when an error on the page overwrites Module
  // (for example, if the order of elements is wrong, and the one defining Module is
  // later), so we save Module and check it later.
  var trueModule = Module;
  function receiveInstantiationResult(result) {
    // 'result' is a ResultObject object which has both the module and instance.
    // receiveInstance() will swap in the exports (to Module.asm) so they can be called
    assert(Module === trueModule, 'the Module object should not be replaced during async compilation - perhaps the order of HTML elements is wrong?');
    trueModule = null;
    // TODO: Due to Closure regression https://github.com/google/closure-compiler/issues/3193, the above line no longer optimizes out down to the following line.
    // When the regression is fixed, can restore the above PTHREADS-enabled path.
    return receiveInstance(result['instance']);
  }

  var info = getWasmImports();

  // User shell pages can write their own Module.instantiateWasm = function(imports, successCallback) callback
  // to manually instantiate the Wasm module themselves. This allows pages to
  // run the instantiation parallel to any other async startup actions they are
  // performing.
  // Also pthreads and wasm workers initialize the wasm instance through this
  // path.
  if (Module['instantiateWasm']) {
    return new Promise((resolve, reject) => {
      try {
        Module['instantiateWasm'](info, (mod, inst) => {
          resolve(receiveInstance(mod, inst));
        });
      } catch(e) {
        err(`Module.instantiateWasm callback failed with error: ${e}`);
        reject(e);
      }
    });
  }

  wasmBinaryFile ??= findWasmBinary();
  try {
    var result = await instantiateAsync(wasmBinary, wasmBinaryFile, info);
    var exports = receiveInstantiationResult(result);
    return exports;
  } catch (e) {
    // If instantiation fails, reject the module ready promise.
    readyPromiseReject(e);
    return Promise.reject(e);
  }
}

// end include: preamble.js

// Begin JS library code


  class ExitStatus {
      name = 'ExitStatus';
      constructor(status) {
        this.message = `Program terminated with exit(${status})`;
        this.status = status;
      }
    }

  var callRuntimeCallbacks = (callbacks) => {
      while (callbacks.length > 0) {
        // Pass the module as the first argument.
        callbacks.shift()(Module);
      }
    };
  var onPostRuns = [];
  var addOnPostRun = (cb) => onPostRuns.push(cb);

  var onPreRuns = [];
  var addOnPreRun = (cb) => onPreRuns.push(cb);

  /** @noinline */
  var base64Decode = (b64) => {
      if (ENVIRONMENT_IS_NODE) {
        var buf = Buffer.from(b64, 'base64');
        return new Uint8Array(buf.buffer, buf.byteOffset, buf.length);
      }
  
      assert(b64.length % 4 == 0);
      var b1, b2, i = 0, j = 0, bLength = b64.length;
      var output = new Uint8Array((bLength*3>>2) - (b64[bLength-2] == '=') - (b64[bLength-1] == '='));
      for (; i < bLength; i += 4, j += 3) {
        b1 = base64ReverseLookup[b64.charCodeAt(i+1)];
        b2 = base64ReverseLookup[b64.charCodeAt(i+2)];
        output[j] = base64ReverseLookup[b64.charCodeAt(i)] << 2 | b1 >> 4;
        output[j+1] = b1 << 4 | b2 >> 2;
        output[j+2] = b2 << 6 | base64ReverseLookup[b64.charCodeAt(i+3)];
      }
      return output;
    };


  
    /**
     * @param {number} ptr
     * @param {string} type
     */
  function getValue(ptr, type = 'i8') {
    if (type.endsWith('*')) type = '*';
    switch (type) {
      case 'i1': return HEAP8[ptr];
      case 'i8': return HEAP8[ptr];
      case 'i16': return HEAP16[((ptr)>>1)];
      case 'i32': return HEAP32[((ptr)>>2)];
      case 'i64': return HEAP64[((ptr)>>3)];
      case 'float': return HEAPF32[((ptr)>>2)];
      case 'double': return HEAPF64[((ptr)>>3)];
      case '*': return HEAPU32[((ptr)>>2)];
      default: abort(`invalid type for getValue: ${type}`);
    }
  }

  var noExitRuntime = true;

  var ptrToString = (ptr) => {
      assert(typeof ptr === 'number');
      // With CAN_ADDRESS_2GB or MEMORY64, pointers are already unsigned.
      ptr >>>= 0;
      return '0x' + ptr.toString(16).padStart(8, '0');
    };

  
    /**
     * @param {number} ptr
     * @param {number} value
     * @param {string} type
     */
  function setValue(ptr, value, type = 'i8') {
    if (type.endsWith('*')) type = '*';
    switch (type) {
      case 'i1': HEAP8[ptr] = value; break;
      case 'i8': HEAP8[ptr] = value; break;
      case 'i16': HEAP16[((ptr)>>1)] = value; break;
      case 'i32': HEAP32[((ptr)>>2)] = value; break;
      case 'i64': HEAP64[((ptr)>>3)] = BigInt(value); break;
      case 'float': HEAPF32[((ptr)>>2)] = value; break;
      case 'double': HEAPF64[((ptr)>>3)] = value; break;
      case '*': HEAPU32[((ptr)>>2)] = value; break;
      default: abort(`invalid type for setValue: ${type}`);
    }
  }

  var stackRestore = (val) => __emscripten_stack_restore(val);

  var stackSave = () => _emscripten_stack_get_current();

  var warnOnce = (text) => {
      warnOnce.shown ||= {};
      if (!warnOnce.shown[text]) {
        warnOnce.shown[text] = 1;
        if (ENVIRONMENT_IS_NODE) text = 'warning: ' + text;
        err(text);
      }
    };

  /** @suppress {duplicate } */
  var syscallGetVarargI = () => {
      assert(SYSCALLS.varargs != undefined);
      // the `+` prepended here is necessary to convince the JSCompiler that varargs is indeed a number.
      var ret = HEAP32[((+SYSCALLS.varargs)>>2)];
      SYSCALLS.varargs += 4;
      return ret;
    };
  var syscallGetVarargP = syscallGetVarargI;
  
  
  var PATH = {
  isAbs:(path) => path.charAt(0) === '/',
  splitPath:(filename) => {
        var splitPathRe = /^(\/?|)([\s\S]*?)((?:\.{1,2}|[^\/]+?|)(\.[^.\/]*|))(?:[\/]*)$/;
        return splitPathRe.exec(filename).slice(1);
      },
  normalizeArray:(parts, allowAboveRoot) => {
        // if the path tries to go above the root, `up` ends up > 0
        var up = 0;
        for (var i = parts.length - 1; i >= 0; i--) {
          var last = parts[i];
          if (last === '.') {
            parts.splice(i, 1);
          } else if (last === '..') {
            parts.splice(i, 1);
            up++;
          } else if (up) {
            parts.splice(i, 1);
            up--;
          }
        }
        // if the path is allowed to go above the root, restore leading ..s
        if (allowAboveRoot) {
          for (; up; up--) {
            parts.unshift('..');
          }
        }
        return parts;
      },
  normalize:(path) => {
        var isAbsolute = PATH.isAbs(path),
            trailingSlash = path.slice(-1) === '/';
        // Normalize the path
        path = PATH.normalizeArray(path.split('/').filter((p) => !!p), !isAbsolute).join('/');
        if (!path && !isAbsolute) {
          path = '.';
        }
        if (path && trailingSlash) {
          path += '/';
        }
        return (isAbsolute ? '/' : '') + path;
      },
  dirname:(path) => {
        var result = PATH.splitPath(path),
            root = result[0],
            dir = result[1];
        if (!root && !dir) {
          // No dirname whatsoever
          return '.';
        }
        if (dir) {
          // It has a dirname, strip trailing slash
          dir = dir.slice(0, -1);
        }
        return root + dir;
      },
  basename:(path) => path && path.match(/([^\/]+|\/)\/*$/)[1],
  join:(...paths) => PATH.normalize(paths.join('/')),
  join2:(l, r) => PATH.normalize(l + '/' + r),
  };
  
  var initRandomFill = () => {
      // This block is not needed on v19+ since crypto.getRandomValues is builtin
      if (ENVIRONMENT_IS_NODE) {
        var nodeCrypto = require('crypto');
        return (view) => nodeCrypto.randomFillSync(view);
      }
  
      return (view) => crypto.getRandomValues(view);
    };
  var randomFill = (view) => {
      // Lazily init on the first invocation.
      (randomFill = initRandomFill())(view);
    };
  
  
  
  var PATH_FS = {
  resolve:(...args) => {
        var resolvedPath = '',
          resolvedAbsolute = false;
        for (var i = args.length - 1; i >= -1 && !resolvedAbsolute; i--) {
          var path = (i >= 0) ? args[i] : FS.cwd();
          // Skip empty and invalid entries
          if (typeof path != 'string') {
            throw new TypeError('Arguments to path.resolve must be strings');
          } else if (!path) {
            return ''; // an invalid portion invalidates the whole thing
          }
          resolvedPath = path + '/' + resolvedPath;
          resolvedAbsolute = PATH.isAbs(path);
        }
        // At this point the path should be resolved to a full absolute path, but
        // handle relative paths to be safe (might happen when process.cwd() fails)
        resolvedPath = PATH.normalizeArray(resolvedPath.split('/').filter((p) => !!p), !resolvedAbsolute).join('/');
        return ((resolvedAbsolute ? '/' : '') + resolvedPath) || '.';
      },
  relative:(from, to) => {
        from = PATH_FS.resolve(from).slice(1);
        to = PATH_FS.resolve(to).slice(1);
        function trim(arr) {
          var start = 0;
          for (; start < arr.length; start++) {
            if (arr[start] !== '') break;
          }
          var end = arr.length - 1;
          for (; end >= 0; end--) {
            if (arr[end] !== '') break;
          }
          if (start > end) return [];
          return arr.slice(start, end - start + 1);
        }
        var fromParts = trim(from.split('/'));
        var toParts = trim(to.split('/'));
        var length = Math.min(fromParts.length, toParts.length);
        var samePartsLength = length;
        for (var i = 0; i < length; i++) {
          if (fromParts[i] !== toParts[i]) {
            samePartsLength = i;
            break;
          }
        }
        var outputParts = [];
        for (var i = samePartsLength; i < fromParts.length; i++) {
          outputParts.push('..');
        }
        outputParts = outputParts.concat(toParts.slice(samePartsLength));
        return outputParts.join('/');
      },
  };
  
  
  var UTF8Decoder = typeof TextDecoder != 'undefined' ? new TextDecoder() : undefined;
  
    /**
     * Given a pointer 'idx' to a null-terminated UTF8-encoded string in the given
     * array that contains uint8 values, returns a copy of that string as a
     * Javascript String object.
     * heapOrArray is either a regular array, or a JavaScript typed array view.
     * @param {number=} idx
     * @param {number=} maxBytesToRead
     * @return {string}
     */
  var UTF8ArrayToString = (heapOrArray, idx = 0, maxBytesToRead = NaN) => {
      var endIdx = idx + maxBytesToRead;
      var endPtr = idx;
      // TextDecoder needs to know the byte length in advance, it doesn't stop on
      // null terminator by itself.  Also, use the length info to avoid running tiny
      // strings through TextDecoder, since .subarray() allocates garbage.
      // (As a tiny code save trick, compare endPtr against endIdx using a negation,
      // so that undefined/NaN means Infinity)
      while (heapOrArray[endPtr] && !(endPtr >= endIdx)) ++endPtr;
  
      // When using conditional TextDecoder, skip it for short strings as the overhead of the native call is not worth it.
      if (endPtr - idx > 16 && heapOrArray.buffer && UTF8Decoder) {
        return UTF8Decoder.decode(heapOrArray.subarray(idx, endPtr));
      }
      var str = '';
      // If building with TextDecoder, we have already computed the string length
      // above, so test loop end condition against that
      while (idx < endPtr) {
        // For UTF8 byte structure, see:
        // http://en.wikipedia.org/wiki/UTF-8#Description
        // https://www.ietf.org/rfc/rfc2279.txt
        // https://tools.ietf.org/html/rfc3629
        var u0 = heapOrArray[idx++];
        if (!(u0 & 0x80)) { str += String.fromCharCode(u0); continue; }
        var u1 = heapOrArray[idx++] & 63;
        if ((u0 & 0xE0) == 0xC0) { str += String.fromCharCode(((u0 & 31) << 6) | u1); continue; }
        var u2 = heapOrArray[idx++] & 63;
        if ((u0 & 0xF0) == 0xE0) {
          u0 = ((u0 & 15) << 12) | (u1 << 6) | u2;
        } else {
          if ((u0 & 0xF8) != 0xF0) warnOnce('Invalid UTF-8 leading byte ' + ptrToString(u0) + ' encountered when deserializing a UTF-8 string in wasm memory to a JS string!');
          u0 = ((u0 & 7) << 18) | (u1 << 12) | (u2 << 6) | (heapOrArray[idx++] & 63);
        }
  
        if (u0 < 0x10000) {
          str += String.fromCharCode(u0);
        } else {
          var ch = u0 - 0x10000;
          str += String.fromCharCode(0xD800 | (ch >> 10), 0xDC00 | (ch & 0x3FF));
        }
      }
      return str;
    };
  
  var FS_stdin_getChar_buffer = [];
  
  var lengthBytesUTF8 = (str) => {
      var len = 0;
      for (var i = 0; i < str.length; ++i) {
        // Gotcha: charCodeAt returns a 16-bit word that is a UTF-16 encoded code
        // unit, not a Unicode code point of the character! So decode
        // UTF16->UTF32->UTF8.
        // See http://unicode.org/faq/utf_bom.html#utf16-3
        var c = str.charCodeAt(i); // possibly a lead surrogate
        if (c <= 0x7F) {
          len++;
        } else if (c <= 0x7FF) {
          len += 2;
        } else if (c >= 0xD800 && c <= 0xDFFF) {
          len += 4; ++i;
        } else {
          len += 3;
        }
      }
      return len;
    };
  
  var stringToUTF8Array = (str, heap, outIdx, maxBytesToWrite) => {
      assert(typeof str === 'string', `stringToUTF8Array expects a string (got ${typeof str})`);
      // Parameter maxBytesToWrite is not optional. Negative values, 0, null,
      // undefined and false each don't write out any bytes.
      if (!(maxBytesToWrite > 0))
        return 0;
  
      var startIdx = outIdx;
      var endIdx = outIdx + maxBytesToWrite - 1; // -1 for string null terminator.
      for (var i = 0; i < str.length; ++i) {
        // Gotcha: charCodeAt returns a 16-bit word that is a UTF-16 encoded code
        // unit, not a Unicode code point of the character! So decode
        // UTF16->UTF32->UTF8.
        // See http://unicode.org/faq/utf_bom.html#utf16-3
        // For UTF8 byte structure, see http://en.wikipedia.org/wiki/UTF-8#Description
        // and https://www.ietf.org/rfc/rfc2279.txt
        // and https://tools.ietf.org/html/rfc3629
        var u = str.charCodeAt(i); // possibly a lead surrogate
        if (u >= 0xD800 && u <= 0xDFFF) {
          var u1 = str.charCodeAt(++i);
          u = 0x10000 + ((u & 0x3FF) << 10) | (u1 & 0x3FF);
        }
        if (u <= 0x7F) {
          if (outIdx >= endIdx) break;
          heap[outIdx++] = u;
        } else if (u <= 0x7FF) {
          if (outIdx + 1 >= endIdx) break;
          heap[outIdx++] = 0xC0 | (u >> 6);
          heap[outIdx++] = 0x80 | (u & 63);
        } else if (u <= 0xFFFF) {
          if (outIdx + 2 >= endIdx) break;
          heap[outIdx++] = 0xE0 | (u >> 12);
          heap[outIdx++] = 0x80 | ((u >> 6) & 63);
          heap[outIdx++] = 0x80 | (u & 63);
        } else {
          if (outIdx + 3 >= endIdx) break;
          if (u > 0x10FFFF) warnOnce('Invalid Unicode code point ' + ptrToString(u) + ' encountered when serializing a JS string to a UTF-8 string in wasm memory! (Valid unicode code points should be in range 0-0x10FFFF).');
          heap[outIdx++] = 0xF0 | (u >> 18);
          heap[outIdx++] = 0x80 | ((u >> 12) & 63);
          heap[outIdx++] = 0x80 | ((u >> 6) & 63);
          heap[outIdx++] = 0x80 | (u & 63);
        }
      }
      // Null-terminate the pointer to the buffer.
      heap[outIdx] = 0;
      return outIdx - startIdx;
    };
  /** @type {function(string, boolean=, number=)} */
  var intArrayFromString = (stringy, dontAddNull, length) => {
      var len = length > 0 ? length : lengthBytesUTF8(stringy)+1;
      var u8array = new Array(len);
      var numBytesWritten = stringToUTF8Array(stringy, u8array, 0, u8array.length);
      if (dontAddNull) u8array.length = numBytesWritten;
      return u8array;
    };
  var FS_stdin_getChar = () => {
      if (!FS_stdin_getChar_buffer.length) {
        var result = null;
        if (ENVIRONMENT_IS_NODE) {
          // we will read data by chunks of BUFSIZE
          var BUFSIZE = 256;
          var buf = Buffer.alloc(BUFSIZE);
          var bytesRead = 0;
  
          // For some reason we must suppress a closure warning here, even though
          // fd definitely exists on process.stdin, and is even the proper way to
          // get the fd of stdin,
          // https://github.com/nodejs/help/issues/2136#issuecomment-523649904
          // This started to happen after moving this logic out of library_tty.js,
          // so it is related to the surrounding code in some unclear manner.
          /** @suppress {missingProperties} */
          var fd = process.stdin.fd;
  
          try {
            bytesRead = fs.readSync(fd, buf, 0, BUFSIZE);
          } catch(e) {
            // Cross-platform differences: on Windows, reading EOF throws an
            // exception, but on other OSes, reading EOF returns 0. Uniformize
            // behavior by treating the EOF exception to return 0.
            if (e.toString().includes('EOF')) bytesRead = 0;
            else throw e;
          }
  
          if (bytesRead > 0) {
            result = buf.slice(0, bytesRead).toString('utf-8');
          }
        } else
        if (typeof window != 'undefined' &&
          typeof window.prompt == 'function') {
          // Browser.
          result = window.prompt('Input: ');  // returns null on cancel
          if (result !== null) {
            result += '\n';
          }
        } else
        {}
        if (!result) {
          return null;
        }
        FS_stdin_getChar_buffer = intArrayFromString(result, true);
      }
      return FS_stdin_getChar_buffer.shift();
    };
  var TTY = {
  ttys:[],
  init() {
        // https://github.com/emscripten-core/emscripten/pull/1555
        // if (ENVIRONMENT_IS_NODE) {
        //   // currently, FS.init does not distinguish if process.stdin is a file or TTY
        //   // device, it always assumes it's a TTY device. because of this, we're forcing
        //   // process.stdin to UTF8 encoding to at least make stdin reading compatible
        //   // with text files until FS.init can be refactored.
        //   process.stdin.setEncoding('utf8');
        // }
      },
  shutdown() {
        // https://github.com/emscripten-core/emscripten/pull/1555
        // if (ENVIRONMENT_IS_NODE) {
        //   // inolen: any idea as to why node -e 'process.stdin.read()' wouldn't exit immediately (with process.stdin being a tty)?
        //   // isaacs: because now it's reading from the stream, you've expressed interest in it, so that read() kicks off a _read() which creates a ReadReq operation
        //   // inolen: I thought read() in that case was a synchronous operation that just grabbed some amount of buffered data if it exists?
        //   // isaacs: it is. but it also triggers a _read() call, which calls readStart() on the handle
        //   // isaacs: do process.stdin.pause() and i'd think it'd probably close the pending call
        //   process.stdin.pause();
        // }
      },
  register(dev, ops) {
        TTY.ttys[dev] = { input: [], output: [], ops: ops };
        FS.registerDevice(dev, TTY.stream_ops);
      },
  stream_ops:{
  open(stream) {
          var tty = TTY.ttys[stream.node.rdev];
          if (!tty) {
            throw new FS.ErrnoError(43);
          }
          stream.tty = tty;
          stream.seekable = false;
        },
  close(stream) {
          // flush any pending line data
          stream.tty.ops.fsync(stream.tty);
        },
  fsync(stream) {
          stream.tty.ops.fsync(stream.tty);
        },
  read(stream, buffer, offset, length, pos /* ignored */) {
          if (!stream.tty || !stream.tty.ops.get_char) {
            throw new FS.ErrnoError(60);
          }
          var bytesRead = 0;
          for (var i = 0; i < length; i++) {
            var result;
            try {
              result = stream.tty.ops.get_char(stream.tty);
            } catch (e) {
              throw new FS.ErrnoError(29);
            }
            if (result === undefined && bytesRead === 0) {
              throw new FS.ErrnoError(6);
            }
            if (result === null || result === undefined) break;
            bytesRead++;
            buffer[offset+i] = result;
          }
          if (bytesRead) {
            stream.node.atime = Date.now();
          }
          return bytesRead;
        },
  write(stream, buffer, offset, length, pos) {
          if (!stream.tty || !stream.tty.ops.put_char) {
            throw new FS.ErrnoError(60);
          }
          try {
            for (var i = 0; i < length; i++) {
              stream.tty.ops.put_char(stream.tty, buffer[offset+i]);
            }
          } catch (e) {
            throw new FS.ErrnoError(29);
          }
          if (length) {
            stream.node.mtime = stream.node.ctime = Date.now();
          }
          return i;
        },
  },
  default_tty_ops:{
  get_char(tty) {
          return FS_stdin_getChar();
        },
  put_char(tty, val) {
          if (val === null || val === 10) {
            out(UTF8ArrayToString(tty.output));
            tty.output = [];
          } else {
            if (val != 0) tty.output.push(val); // val == 0 would cut text output off in the middle.
          }
        },
  fsync(tty) {
          if (tty.output?.length > 0) {
            out(UTF8ArrayToString(tty.output));
            tty.output = [];
          }
        },
  ioctl_tcgets(tty) {
          // typical setting
          return {
            c_iflag: 25856,
            c_oflag: 5,
            c_cflag: 191,
            c_lflag: 35387,
            c_cc: [
              0x03, 0x1c, 0x7f, 0x15, 0x04, 0x00, 0x01, 0x00, 0x11, 0x13, 0x1a, 0x00,
              0x12, 0x0f, 0x17, 0x16, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
              0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            ]
          };
        },
  ioctl_tcsets(tty, optional_actions, data) {
          // currently just ignore
          return 0;
        },
  ioctl_tiocgwinsz(tty) {
          return [24, 80];
        },
  },
  default_tty1_ops:{
  put_char(tty, val) {
          if (val === null || val === 10) {
            err(UTF8ArrayToString(tty.output));
            tty.output = [];
          } else {
            if (val != 0) tty.output.push(val);
          }
        },
  fsync(tty) {
          if (tty.output?.length > 0) {
            err(UTF8ArrayToString(tty.output));
            tty.output = [];
          }
        },
  },
  };
  
  
  var mmapAlloc = (size) => {
      abort('internal error: mmapAlloc called but `emscripten_builtin_memalign` native symbol not exported');
    };
  var MEMFS = {
  ops_table:null,
  mount(mount) {
        return MEMFS.createNode(null, '/', 16895, 0);
      },
  createNode(parent, name, mode, dev) {
        if (FS.isBlkdev(mode) || FS.isFIFO(mode)) {
          // no supported
          throw new FS.ErrnoError(63);
        }
        MEMFS.ops_table ||= {
          dir: {
            node: {
              getattr: MEMFS.node_ops.getattr,
              setattr: MEMFS.node_ops.setattr,
              lookup: MEMFS.node_ops.lookup,
              mknod: MEMFS.node_ops.mknod,
              rename: MEMFS.node_ops.rename,
              unlink: MEMFS.node_ops.unlink,
              rmdir: MEMFS.node_ops.rmdir,
              readdir: MEMFS.node_ops.readdir,
              symlink: MEMFS.node_ops.symlink
            },
            stream: {
              llseek: MEMFS.stream_ops.llseek
            }
          },
          file: {
            node: {
              getattr: MEMFS.node_ops.getattr,
              setattr: MEMFS.node_ops.setattr
            },
            stream: {
              llseek: MEMFS.stream_ops.llseek,
              read: MEMFS.stream_ops.read,
              write: MEMFS.stream_ops.write,
              mmap: MEMFS.stream_ops.mmap,
              msync: MEMFS.stream_ops.msync
            }
          },
          link: {
            node: {
              getattr: MEMFS.node_ops.getattr,
              setattr: MEMFS.node_ops.setattr,
              readlink: MEMFS.node_ops.readlink
            },
            stream: {}
          },
          chrdev: {
            node: {
              getattr: MEMFS.node_ops.getattr,
              setattr: MEMFS.node_ops.setattr
            },
            stream: FS.chrdev_stream_ops
          }
        };
        var node = FS.createNode(parent, name, mode, dev);
        if (FS.isDir(node.mode)) {
          node.node_ops = MEMFS.ops_table.dir.node;
          node.stream_ops = MEMFS.ops_table.dir.stream;
          node.contents = {};
        } else if (FS.isFile(node.mode)) {
          node.node_ops = MEMFS.ops_table.file.node;
          node.stream_ops = MEMFS.ops_table.file.stream;
          node.usedBytes = 0; // The actual number of bytes used in the typed array, as opposed to contents.length which gives the whole capacity.
          // When the byte data of the file is populated, this will point to either a typed array, or a normal JS array. Typed arrays are preferred
          // for performance, and used by default. However, typed arrays are not resizable like normal JS arrays are, so there is a small disk size
          // penalty involved for appending file writes that continuously grow a file similar to std::vector capacity vs used -scheme.
          node.contents = null; 
        } else if (FS.isLink(node.mode)) {
          node.node_ops = MEMFS.ops_table.link.node;
          node.stream_ops = MEMFS.ops_table.link.stream;
        } else if (FS.isChrdev(node.mode)) {
          node.node_ops = MEMFS.ops_table.chrdev.node;
          node.stream_ops = MEMFS.ops_table.chrdev.stream;
        }
        node.atime = node.mtime = node.ctime = Date.now();
        // add the new node to the parent
        if (parent) {
          parent.contents[name] = node;
          parent.atime = parent.mtime = parent.ctime = node.atime;
        }
        return node;
      },
  getFileDataAsTypedArray(node) {
        if (!node.contents) return new Uint8Array(0);
        if (node.contents.subarray) return node.contents.subarray(0, node.usedBytes); // Make sure to not return excess unused bytes.
        return new Uint8Array(node.contents);
      },
  expandFileStorage(node, newCapacity) {
        var prevCapacity = node.contents ? node.contents.length : 0;
        if (prevCapacity >= newCapacity) return; // No need to expand, the storage was already large enough.
        // Don't expand strictly to the given requested limit if it's only a very small increase, but instead geometrically grow capacity.
        // For small filesizes (<1MB), perform size*2 geometric increase, but for large sizes, do a much more conservative size*1.125 increase to
        // avoid overshooting the allocation cap by a very large margin.
        var CAPACITY_DOUBLING_MAX = 1024 * 1024;
        newCapacity = Math.max(newCapacity, (prevCapacity * (prevCapacity < CAPACITY_DOUBLING_MAX ? 2.0 : 1.125)) >>> 0);
        if (prevCapacity != 0) newCapacity = Math.max(newCapacity, 256); // At minimum allocate 256b for each file when expanding.
        var oldContents = node.contents;
        node.contents = new Uint8Array(newCapacity); // Allocate new storage.
        if (node.usedBytes > 0) node.contents.set(oldContents.subarray(0, node.usedBytes), 0); // Copy old data over to the new storage.
      },
  resizeFileStorage(node, newSize) {
        if (node.usedBytes == newSize) return;
        if (newSize == 0) {
          node.contents = null; // Fully decommit when requesting a resize to zero.
          node.usedBytes = 0;
        } else {
          var oldContents = node.contents;
          node.contents = new Uint8Array(newSize); // Allocate new storage.
          if (oldContents) {
            node.contents.set(oldContents.subarray(0, Math.min(newSize, node.usedBytes))); // Copy old data over to the new storage.
          }
          node.usedBytes = newSize;
        }
      },
  node_ops:{
  getattr(node) {
          var attr = {};
          // device numbers reuse inode numbers.
          attr.dev = FS.isChrdev(node.mode) ? node.id : 1;
          attr.ino = node.id;
          attr.mode = node.mode;
          attr.nlink = 1;
          attr.uid = 0;
          attr.gid = 0;
          attr.rdev = node.rdev;
          if (FS.isDir(node.mode)) {
            attr.size = 4096;
          } else if (FS.isFile(node.mode)) {
            attr.size = node.usedBytes;
          } else if (FS.isLink(node.mode)) {
            attr.size = node.link.length;
          } else {
            attr.size = 0;
          }
          attr.atime = new Date(node.atime);
          attr.mtime = new Date(node.mtime);
          attr.ctime = new Date(node.ctime);
          // NOTE: In our implementation, st_blocks = Math.ceil(st_size/st_blksize),
          //       but this is not required by the standard.
          attr.blksize = 4096;
          attr.blocks = Math.ceil(attr.size / attr.blksize);
          return attr;
        },
  setattr(node, attr) {
          for (const key of ["mode", "atime", "mtime", "ctime"]) {
            if (attr[key] != null) {
              node[key] = attr[key];
            }
          }
          if (attr.size !== undefined) {
            MEMFS.resizeFileStorage(node, attr.size);
          }
        },
  lookup(parent, name) {
          throw new FS.ErrnoError(44);
        },
  mknod(parent, name, mode, dev) {
          return MEMFS.createNode(parent, name, mode, dev);
        },
  rename(old_node, new_dir, new_name) {
          var new_node;
          try {
            new_node = FS.lookupNode(new_dir, new_name);
          } catch (e) {}
          if (new_node) {
            if (FS.isDir(old_node.mode)) {
              // if we're overwriting a directory at new_name, make sure it's empty.
              for (var i in new_node.contents) {
                throw new FS.ErrnoError(55);
              }
            }
            FS.hashRemoveNode(new_node);
          }
          // do the internal rewiring
          delete old_node.parent.contents[old_node.name];
          new_dir.contents[new_name] = old_node;
          old_node.name = new_name;
          new_dir.ctime = new_dir.mtime = old_node.parent.ctime = old_node.parent.mtime = Date.now();
        },
  unlink(parent, name) {
          delete parent.contents[name];
          parent.ctime = parent.mtime = Date.now();
        },
  rmdir(parent, name) {
          var node = FS.lookupNode(parent, name);
          for (var i in node.contents) {
            throw new FS.ErrnoError(55);
          }
          delete parent.contents[name];
          parent.ctime = parent.mtime = Date.now();
        },
  readdir(node) {
          return ['.', '..', ...Object.keys(node.contents)];
        },
  symlink(parent, newname, oldpath) {
          var node = MEMFS.createNode(parent, newname, 0o777 | 40960, 0);
          node.link = oldpath;
          return node;
        },
  readlink(node) {
          if (!FS.isLink(node.mode)) {
            throw new FS.ErrnoError(28);
          }
          return node.link;
        },
  },
  stream_ops:{
  read(stream, buffer, offset, length, position) {
          var contents = stream.node.contents;
          if (position >= stream.node.usedBytes) return 0;
          var size = Math.min(stream.node.usedBytes - position, length);
          assert(size >= 0);
          if (size > 8 && contents.subarray) { // non-trivial, and typed array
            buffer.set(contents.subarray(position, position + size), offset);
          } else {
            for (var i = 0; i < size; i++) buffer[offset + i] = contents[position + i];
          }
          return size;
        },
  write(stream, buffer, offset, length, position, canOwn) {
          // The data buffer should be a typed array view
          assert(!(buffer instanceof ArrayBuffer));
          // If the buffer is located in main memory (HEAP), and if
          // memory can grow, we can't hold on to references of the
          // memory buffer, as they may get invalidated. That means we
          // need to do copy its contents.
          if (buffer.buffer === HEAP8.buffer) {
            canOwn = false;
          }
  
          if (!length) return 0;
          var node = stream.node;
          node.mtime = node.ctime = Date.now();
  
          if (buffer.subarray && (!node.contents || node.contents.subarray)) { // This write is from a typed array to a typed array?
            if (canOwn) {
              assert(position === 0, 'canOwn must imply no weird position inside the file');
              node.contents = buffer.subarray(offset, offset + length);
              node.usedBytes = length;
              return length;
            } else if (node.usedBytes === 0 && position === 0) { // If this is a simple first write to an empty file, do a fast set since we don't need to care about old data.
              node.contents = buffer.slice(offset, offset + length);
              node.usedBytes = length;
              return length;
            } else if (position + length <= node.usedBytes) { // Writing to an already allocated and used subrange of the file?
              node.contents.set(buffer.subarray(offset, offset + length), position);
              return length;
            }
          }
  
          // Appending to an existing file and we need to reallocate, or source data did not come as a typed array.
          MEMFS.expandFileStorage(node, position+length);
          if (node.contents.subarray && buffer.subarray) {
            // Use typed array write which is available.
            node.contents.set(buffer.subarray(offset, offset + length), position);
          } else {
            for (var i = 0; i < length; i++) {
             node.contents[position + i] = buffer[offset + i]; // Or fall back to manual write if not.
            }
          }
          node.usedBytes = Math.max(node.usedBytes, position + length);
          return length;
        },
  llseek(stream, offset, whence) {
          var position = offset;
          if (whence === 1) {
            position += stream.position;
          } else if (whence === 2) {
            if (FS.isFile(stream.node.mode)) {
              position += stream.node.usedBytes;
            }
          }
          if (position < 0) {
            throw new FS.ErrnoError(28);
          }
          return position;
        },
  mmap(stream, length, position, prot, flags) {
          if (!FS.isFile(stream.node.mode)) {
            throw new FS.ErrnoError(43);
          }
          var ptr;
          var allocated;
          var contents = stream.node.contents;
          // Only make a new copy when MAP_PRIVATE is specified.
          if (!(flags & 2) && contents && contents.buffer === HEAP8.buffer) {
            // We can't emulate MAP_SHARED when the file is not backed by the
            // buffer we're mapping to (e.g. the HEAP buffer).
            allocated = false;
            ptr = contents.byteOffset;
          } else {
            allocated = true;
            ptr = mmapAlloc(length);
            if (!ptr) {
              throw new FS.ErrnoError(48);
            }
            if (contents) {
              // Try to avoid unnecessary slices.
              if (position > 0 || position + length < contents.length) {
                if (contents.subarray) {
                  contents = contents.subarray(position, position + length);
                } else {
                  contents = Array.prototype.slice.call(contents, position, position + length);
                }
              }
              HEAP8.set(contents, ptr);
            }
          }
          return { ptr, allocated };
        },
  msync(stream, buffer, offset, length, mmapFlags) {
          MEMFS.stream_ops.write(stream, buffer, 0, length, offset, false);
          // should we check if bytesWritten and length are the same?
          return 0;
        },
  },
  };
  
  var asyncLoad = async (url) => {
      var arrayBuffer = await readAsync(url);
      assert(arrayBuffer, `Loading data file "${url}" failed (no arrayBuffer).`);
      return new Uint8Array(arrayBuffer);
    };
  
  
  var FS_createDataFile = (...args) => FS.createDataFile(...args);
  
  var preloadPlugins = [];
  var FS_handledByPreloadPlugin = (byteArray, fullname, finish, onerror) => {
      // Ensure plugins are ready.
      if (typeof Browser != 'undefined') Browser.init();
  
      var handled = false;
      preloadPlugins.forEach((plugin) => {
        if (handled) return;
        if (plugin['canHandle'](fullname)) {
          plugin['handle'](byteArray, fullname, finish, onerror);
          handled = true;
        }
      });
      return handled;
    };
  var FS_createPreloadedFile = (parent, name, url, canRead, canWrite, onload, onerror, dontCreateFile, canOwn, preFinish) => {
      // TODO we should allow people to just pass in a complete filename instead
      // of parent and name being that we just join them anyways
      var fullname = name ? PATH_FS.resolve(PATH.join2(parent, name)) : parent;
      var dep = getUniqueRunDependency(`cp ${fullname}`); // might have several active requests for the same fullname
      function processData(byteArray) {
        function finish(byteArray) {
          preFinish?.();
          if (!dontCreateFile) {
            FS_createDataFile(parent, name, byteArray, canRead, canWrite, canOwn);
          }
          onload?.();
          removeRunDependency(dep);
        }
        if (FS_handledByPreloadPlugin(byteArray, fullname, finish, () => {
          onerror?.();
          removeRunDependency(dep);
        })) {
          return;
        }
        finish(byteArray);
      }
      addRunDependency(dep);
      if (typeof url == 'string') {
        asyncLoad(url).then(processData, onerror);
      } else {
        processData(url);
      }
    };
  
  var FS_modeStringToFlags = (str) => {
      var flagModes = {
        'r': 0,
        'r+': 2,
        'w': 512 | 64 | 1,
        'w+': 512 | 64 | 2,
        'a': 1024 | 64 | 1,
        'a+': 1024 | 64 | 2,
      };
      var flags = flagModes[str];
      if (typeof flags == 'undefined') {
        throw new Error(`Unknown file open mode: ${str}`);
      }
      return flags;
    };
  
  var FS_getMode = (canRead, canWrite) => {
      var mode = 0;
      if (canRead) mode |= 292 | 73;
      if (canWrite) mode |= 146;
      return mode;
    };
  
  
  
  
  
  
    /**
     * Given a pointer 'ptr' to a null-terminated UTF8-encoded string in the
     * emscripten HEAP, returns a copy of that string as a Javascript String object.
     *
     * @param {number} ptr
     * @param {number=} maxBytesToRead - An optional length that specifies the
     *   maximum number of bytes to read. You can omit this parameter to scan the
     *   string until the first 0 byte. If maxBytesToRead is passed, and the string
     *   at [ptr, ptr+maxBytesToReadr[ contains a null byte in the middle, then the
     *   string will cut short at that byte index (i.e. maxBytesToRead will not
     *   produce a string of exact length [ptr, ptr+maxBytesToRead[) N.B. mixing
     *   frequent uses of UTF8ToString() with and without maxBytesToRead may throw
     *   JS JIT optimizations off, so it is worth to consider consistently using one
     * @return {string}
     */
  var UTF8ToString = (ptr, maxBytesToRead) => {
      assert(typeof ptr == 'number', `UTF8ToString expects a number (got ${typeof ptr})`);
      return ptr ? UTF8ArrayToString(HEAPU8, ptr, maxBytesToRead) : '';
    };
  
  var strError = (errno) => UTF8ToString(_strerror(errno));
  
  var ERRNO_CODES = {
      'EPERM': 63,
      'ENOENT': 44,
      'ESRCH': 71,
      'EINTR': 27,
      'EIO': 29,
      'ENXIO': 60,
      'E2BIG': 1,
      'ENOEXEC': 45,
      'EBADF': 8,
      'ECHILD': 12,
      'EAGAIN': 6,
      'EWOULDBLOCK': 6,
      'ENOMEM': 48,
      'EACCES': 2,
      'EFAULT': 21,
      'ENOTBLK': 105,
      'EBUSY': 10,
      'EEXIST': 20,
      'EXDEV': 75,
      'ENODEV': 43,
      'ENOTDIR': 54,
      'EISDIR': 31,
      'EINVAL': 28,
      'ENFILE': 41,
      'EMFILE': 33,
      'ENOTTY': 59,
      'ETXTBSY': 74,
      'EFBIG': 22,
      'ENOSPC': 51,
      'ESPIPE': 70,
      'EROFS': 69,
      'EMLINK': 34,
      'EPIPE': 64,
      'EDOM': 18,
      'ERANGE': 68,
      'ENOMSG': 49,
      'EIDRM': 24,
      'ECHRNG': 106,
      'EL2NSYNC': 156,
      'EL3HLT': 107,
      'EL3RST': 108,
      'ELNRNG': 109,
      'EUNATCH': 110,
      'ENOCSI': 111,
      'EL2HLT': 112,
      'EDEADLK': 16,
      'ENOLCK': 46,
      'EBADE': 113,
      'EBADR': 114,
      'EXFULL': 115,
      'ENOANO': 104,
      'EBADRQC': 103,
      'EBADSLT': 102,
      'EDEADLOCK': 16,
      'EBFONT': 101,
      'ENOSTR': 100,
      'ENODATA': 116,
      'ETIME': 117,
      'ENOSR': 118,
      'ENONET': 119,
      'ENOPKG': 120,
      'EREMOTE': 121,
      'ENOLINK': 47,
      'EADV': 122,
      'ESRMNT': 123,
      'ECOMM': 124,
      'EPROTO': 65,
      'EMULTIHOP': 36,
      'EDOTDOT': 125,
      'EBADMSG': 9,
      'ENOTUNIQ': 126,
      'EBADFD': 127,
      'EREMCHG': 128,
      'ELIBACC': 129,
      'ELIBBAD': 130,
      'ELIBSCN': 131,
      'ELIBMAX': 132,
      'ELIBEXEC': 133,
      'ENOSYS': 52,
      'ENOTEMPTY': 55,
      'ENAMETOOLONG': 37,
      'ELOOP': 32,
      'EOPNOTSUPP': 138,
      'EPFNOSUPPORT': 139,
      'ECONNRESET': 15,
      'ENOBUFS': 42,
      'EAFNOSUPPORT': 5,
      'EPROTOTYPE': 67,
      'ENOTSOCK': 57,
      'ENOPROTOOPT': 50,
      'ESHUTDOWN': 140,
      'ECONNREFUSED': 14,
      'EADDRINUSE': 3,
      'ECONNABORTED': 13,
      'ENETUNREACH': 40,
      'ENETDOWN': 38,
      'ETIMEDOUT': 73,
      'EHOSTDOWN': 142,
      'EHOSTUNREACH': 23,
      'EINPROGRESS': 26,
      'EALREADY': 7,
      'EDESTADDRREQ': 17,
      'EMSGSIZE': 35,
      'EPROTONOSUPPORT': 66,
      'ESOCKTNOSUPPORT': 137,
      'EADDRNOTAVAIL': 4,
      'ENETRESET': 39,
      'EISCONN': 30,
      'ENOTCONN': 53,
      'ETOOMANYREFS': 141,
      'EUSERS': 136,
      'EDQUOT': 19,
      'ESTALE': 72,
      'ENOTSUP': 138,
      'ENOMEDIUM': 148,
      'EILSEQ': 25,
      'EOVERFLOW': 61,
      'ECANCELED': 11,
      'ENOTRECOVERABLE': 56,
      'EOWNERDEAD': 62,
      'ESTRPIPE': 135,
    };
  var FS = {
  root:null,
  mounts:[],
  devices:{
  },
  streams:[],
  nextInode:1,
  nameTable:null,
  currentPath:"/",
  initialized:false,
  ignorePermissions:true,
  filesystems:null,
  syncFSRequests:0,
  readFiles:{
  },
  ErrnoError:class extends Error {
        name = 'ErrnoError';
        // We set the `name` property to be able to identify `FS.ErrnoError`
        // - the `name` is a standard ECMA-262 property of error objects. Kind of good to have it anyway.
        // - when using PROXYFS, an error can come from an underlying FS
        // as different FS objects have their own FS.ErrnoError each,
        // the test `err instanceof FS.ErrnoError` won't detect an error coming from another filesystem, causing bugs.
        // we'll use the reliable test `err.name == "ErrnoError"` instead
        constructor(errno) {
          super(runtimeInitialized ? strError(errno) : '');
          this.errno = errno;
          for (var key in ERRNO_CODES) {
            if (ERRNO_CODES[key] === errno) {
              this.code = key;
              break;
            }
          }
        }
      },
  FSStream:class {
        shared = {};
        get object() {
          return this.node;
        }
        set object(val) {
          this.node = val;
        }
        get isRead() {
          return (this.flags & 2097155) !== 1;
        }
        get isWrite() {
          return (this.flags & 2097155) !== 0;
        }
        get isAppend() {
          return (this.flags & 1024);
        }
        get flags() {
          return this.shared.flags;
        }
        set flags(val) {
          this.shared.flags = val;
        }
        get position() {
          return this.shared.position;
        }
        set position(val) {
          this.shared.position = val;
        }
      },
  FSNode:class {
        node_ops = {};
        stream_ops = {};
        readMode = 292 | 73;
        writeMode = 146;
        mounted = null;
        constructor(parent, name, mode, rdev) {
          if (!parent) {
            parent = this;  // root node sets parent to itself
          }
          this.parent = parent;
          this.mount = parent.mount;
          this.id = FS.nextInode++;
          this.name = name;
          this.mode = mode;
          this.rdev = rdev;
          this.atime = this.mtime = this.ctime = Date.now();
        }
        get read() {
          return (this.mode & this.readMode) === this.readMode;
        }
        set read(val) {
          val ? this.mode |= this.readMode : this.mode &= ~this.readMode;
        }
        get write() {
          return (this.mode & this.writeMode) === this.writeMode;
        }
        set write(val) {
          val ? this.mode |= this.writeMode : this.mode &= ~this.writeMode;
        }
        get isFolder() {
          return FS.isDir(this.mode);
        }
        get isDevice() {
          return FS.isChrdev(this.mode);
        }
      },
  lookupPath(path, opts = {}) {
        if (!path) {
          throw new FS.ErrnoError(44);
        }
        opts.follow_mount ??= true
  
        if (!PATH.isAbs(path)) {
          path = FS.cwd() + '/' + path;
        }
  
        // limit max consecutive symlinks to 40 (SYMLOOP_MAX).
        linkloop: for (var nlinks = 0; nlinks < 40; nlinks++) {
          // split the absolute path
          var parts = path.split('/').filter((p) => !!p);
  
          // start at the root
          var current = FS.root;
          var current_path = '/';
  
          for (var i = 0; i < parts.length; i++) {
            var islast = (i === parts.length-1);
            if (islast && opts.parent) {
              // stop resolving
              break;
            }
  
            if (parts[i] === '.') {
              continue;
            }
  
            if (parts[i] === '..') {
              current_path = PATH.dirname(current_path);
              if (FS.isRoot(current)) {
                path = current_path + '/' + parts.slice(i + 1).join('/');
                continue linkloop;
              } else {
                current = current.parent;
              }
              continue;
            }
  
            current_path = PATH.join2(current_path, parts[i]);
            try {
              current = FS.lookupNode(current, parts[i]);
            } catch (e) {
              // if noent_okay is true, suppress a ENOENT in the last component
              // and return an object with an undefined node. This is needed for
              // resolving symlinks in the path when creating a file.
              if ((e?.errno === 44) && islast && opts.noent_okay) {
                return { path: current_path };
              }
              throw e;
            }
  
            // jump to the mount's root node if this is a mountpoint
            if (FS.isMountpoint(current) && (!islast || opts.follow_mount)) {
              current = current.mounted.root;
            }
  
            // by default, lookupPath will not follow a symlink if it is the final path component.
            // setting opts.follow = true will override this behavior.
            if (FS.isLink(current.mode) && (!islast || opts.follow)) {
              if (!current.node_ops.readlink) {
                throw new FS.ErrnoError(52);
              }
              var link = current.node_ops.readlink(current);
              if (!PATH.isAbs(link)) {
                link = PATH.dirname(current_path) + '/' + link;
              }
              path = link + '/' + parts.slice(i + 1).join('/');
              continue linkloop;
            }
          }
          return { path: current_path, node: current };
        }
        throw new FS.ErrnoError(32);
      },
  getPath(node) {
        var path;
        while (true) {
          if (FS.isRoot(node)) {
            var mount = node.mount.mountpoint;
            if (!path) return mount;
            return mount[mount.length-1] !== '/' ? `${mount}/${path}` : mount + path;
          }
          path = path ? `${node.name}/${path}` : node.name;
          node = node.parent;
        }
      },
  hashName(parentid, name) {
        var hash = 0;
  
        for (var i = 0; i < name.length; i++) {
          hash = ((hash << 5) - hash + name.charCodeAt(i)) | 0;
        }
        return ((parentid + hash) >>> 0) % FS.nameTable.length;
      },
  hashAddNode(node) {
        var hash = FS.hashName(node.parent.id, node.name);
        node.name_next = FS.nameTable[hash];
        FS.nameTable[hash] = node;
      },
  hashRemoveNode(node) {
        var hash = FS.hashName(node.parent.id, node.name);
        if (FS.nameTable[hash] === node) {
          FS.nameTable[hash] = node.name_next;
        } else {
          var current = FS.nameTable[hash];
          while (current) {
            if (current.name_next === node) {
              current.name_next = node.name_next;
              break;
            }
            current = current.name_next;
          }
        }
      },
  lookupNode(parent, name) {
        var errCode = FS.mayLookup(parent);
        if (errCode) {
          throw new FS.ErrnoError(errCode);
        }
        var hash = FS.hashName(parent.id, name);
        for (var node = FS.nameTable[hash]; node; node = node.name_next) {
          var nodeName = node.name;
          if (node.parent.id === parent.id && nodeName === name) {
            return node;
          }
        }
        // if we failed to find it in the cache, call into the VFS
        return FS.lookup(parent, name);
      },
  createNode(parent, name, mode, rdev) {
        assert(typeof parent == 'object')
        var node = new FS.FSNode(parent, name, mode, rdev);
  
        FS.hashAddNode(node);
  
        return node;
      },
  destroyNode(node) {
        FS.hashRemoveNode(node);
      },
  isRoot(node) {
        return node === node.parent;
      },
  isMountpoint(node) {
        return !!node.mounted;
      },
  isFile(mode) {
        return (mode & 61440) === 32768;
      },
  isDir(mode) {
        return (mode & 61440) === 16384;
      },
  isLink(mode) {
        return (mode & 61440) === 40960;
      },
  isChrdev(mode) {
        return (mode & 61440) === 8192;
      },
  isBlkdev(mode) {
        return (mode & 61440) === 24576;
      },
  isFIFO(mode) {
        return (mode & 61440) === 4096;
      },
  isSocket(mode) {
        return (mode & 49152) === 49152;
      },
  flagsToPermissionString(flag) {
        var perms = ['r', 'w', 'rw'][flag & 3];
        if ((flag & 512)) {
          perms += 'w';
        }
        return perms;
      },
  nodePermissions(node, perms) {
        if (FS.ignorePermissions) {
          return 0;
        }
        // return 0 if any user, group or owner bits are set.
        if (perms.includes('r') && !(node.mode & 292)) {
          return 2;
        } else if (perms.includes('w') && !(node.mode & 146)) {
          return 2;
        } else if (perms.includes('x') && !(node.mode & 73)) {
          return 2;
        }
        return 0;
      },
  mayLookup(dir) {
        if (!FS.isDir(dir.mode)) return 54;
        var errCode = FS.nodePermissions(dir, 'x');
        if (errCode) return errCode;
        if (!dir.node_ops.lookup) return 2;
        return 0;
      },
  mayCreate(dir, name) {
        if (!FS.isDir(dir.mode)) {
          return 54;
        }
        try {
          var node = FS.lookupNode(dir, name);
          return 20;
        } catch (e) {
        }
        return FS.nodePermissions(dir, 'wx');
      },
  mayDelete(dir, name, isdir) {
        var node;
        try {
          node = FS.lookupNode(dir, name);
        } catch (e) {
          return e.errno;
        }
        var errCode = FS.nodePermissions(dir, 'wx');
        if (errCode) {
          return errCode;
        }
        if (isdir) {
          if (!FS.isDir(node.mode)) {
            return 54;
          }
          if (FS.isRoot(node) || FS.getPath(node) === FS.cwd()) {
            return 10;
          }
        } else {
          if (FS.isDir(node.mode)) {
            return 31;
          }
        }
        return 0;
      },
  mayOpen(node, flags) {
        if (!node) {
          return 44;
        }
        if (FS.isLink(node.mode)) {
          return 32;
        } else if (FS.isDir(node.mode)) {
          if (FS.flagsToPermissionString(flags) !== 'r' // opening for write
              || (flags & (512 | 64))) { // TODO: check for O_SEARCH? (== search for dir only)
            return 31;
          }
        }
        return FS.nodePermissions(node, FS.flagsToPermissionString(flags));
      },
  checkOpExists(op, err) {
        if (!op) {
          throw new FS.ErrnoError(err);
        }
        return op;
      },
  MAX_OPEN_FDS:4096,
  nextfd() {
        for (var fd = 0; fd <= FS.MAX_OPEN_FDS; fd++) {
          if (!FS.streams[fd]) {
            return fd;
          }
        }
        throw new FS.ErrnoError(33);
      },
  getStreamChecked(fd) {
        var stream = FS.getStream(fd);
        if (!stream) {
          throw new FS.ErrnoError(8);
        }
        return stream;
      },
  getStream:(fd) => FS.streams[fd],
  createStream(stream, fd = -1) {
        assert(fd >= -1);
  
        // clone it, so we can return an instance of FSStream
        stream = Object.assign(new FS.FSStream(), stream);
        if (fd == -1) {
          fd = FS.nextfd();
        }
        stream.fd = fd;
        FS.streams[fd] = stream;
        return stream;
      },
  closeStream(fd) {
        FS.streams[fd] = null;
      },
  dupStream(origStream, fd = -1) {
        var stream = FS.createStream(origStream, fd);
        stream.stream_ops?.dup?.(stream);
        return stream;
      },
  doSetAttr(stream, node, attr) {
        var setattr = stream?.stream_ops.setattr;
        var arg = setattr ? stream : node;
        setattr ??= node.node_ops.setattr;
        FS.checkOpExists(setattr, 63)
        setattr(arg, attr);
      },
  chrdev_stream_ops:{
  open(stream) {
          var device = FS.getDevice(stream.node.rdev);
          // override node's stream ops with the device's
          stream.stream_ops = device.stream_ops;
          // forward the open call
          stream.stream_ops.open?.(stream);
        },
  llseek() {
          throw new FS.ErrnoError(70);
        },
  },
  major:(dev) => ((dev) >> 8),
  minor:(dev) => ((dev) & 0xff),
  makedev:(ma, mi) => ((ma) << 8 | (mi)),
  registerDevice(dev, ops) {
        FS.devices[dev] = { stream_ops: ops };
      },
  getDevice:(dev) => FS.devices[dev],
  getMounts(mount) {
        var mounts = [];
        var check = [mount];
  
        while (check.length) {
          var m = check.pop();
  
          mounts.push(m);
  
          check.push(...m.mounts);
        }
  
        return mounts;
      },
  syncfs(populate, callback) {
        if (typeof populate == 'function') {
          callback = populate;
          populate = false;
        }
  
        FS.syncFSRequests++;
  
        if (FS.syncFSRequests > 1) {
          err(`warning: ${FS.syncFSRequests} FS.syncfs operations in flight at once, probably just doing extra work`);
        }
  
        var mounts = FS.getMounts(FS.root.mount);
        var completed = 0;
  
        function doCallback(errCode) {
          assert(FS.syncFSRequests > 0);
          FS.syncFSRequests--;
          return callback(errCode);
        }
  
        function done(errCode) {
          if (errCode) {
            if (!done.errored) {
              done.errored = true;
              return doCallback(errCode);
            }
            return;
          }
          if (++completed >= mounts.length) {
            doCallback(null);
          }
        };
  
        // sync all mounts
        mounts.forEach((mount) => {
          if (!mount.type.syncfs) {
            return done(null);
          }
          mount.type.syncfs(mount, populate, done);
        });
      },
  mount(type, opts, mountpoint) {
        if (typeof type == 'string') {
          // The filesystem was not included, and instead we have an error
          // message stored in the variable.
          throw type;
        }
        var root = mountpoint === '/';
        var pseudo = !mountpoint;
        var node;
  
        if (root && FS.root) {
          throw new FS.ErrnoError(10);
        } else if (!root && !pseudo) {
          var lookup = FS.lookupPath(mountpoint, { follow_mount: false });
  
          mountpoint = lookup.path;  // use the absolute path
          node = lookup.node;
  
          if (FS.isMountpoint(node)) {
            throw new FS.ErrnoError(10);
          }
  
          if (!FS.isDir(node.mode)) {
            throw new FS.ErrnoError(54);
          }
        }
  
        var mount = {
          type,
          opts,
          mountpoint,
          mounts: []
        };
  
        // create a root node for the fs
        var mountRoot = type.mount(mount);
        mountRoot.mount = mount;
        mount.root = mountRoot;
  
        if (root) {
          FS.root = mountRoot;
        } else if (node) {
          // set as a mountpoint
          node.mounted = mount;
  
          // add the new mount to the current mount's children
          if (node.mount) {
            node.mount.mounts.push(mount);
          }
        }
  
        return mountRoot;
      },
  unmount(mountpoint) {
        var lookup = FS.lookupPath(mountpoint, { follow_mount: false });
  
        if (!FS.isMountpoint(lookup.node)) {
          throw new FS.ErrnoError(28);
        }
  
        // destroy the nodes for this mount, and all its child mounts
        var node = lookup.node;
        var mount = node.mounted;
        var mounts = FS.getMounts(mount);
  
        Object.keys(FS.nameTable).forEach((hash) => {
          var current = FS.nameTable[hash];
  
          while (current) {
            var next = current.name_next;
  
            if (mounts.includes(current.mount)) {
              FS.destroyNode(current);
            }
  
            current = next;
          }
        });
  
        // no longer a mountpoint
        node.mounted = null;
  
        // remove this mount from the child mounts
        var idx = node.mount.mounts.indexOf(mount);
        assert(idx !== -1);
        node.mount.mounts.splice(idx, 1);
      },
  lookup(parent, name) {
        return parent.node_ops.lookup(parent, name);
      },
  mknod(path, mode, dev) {
        var lookup = FS.lookupPath(path, { parent: true });
        var parent = lookup.node;
        var name = PATH.basename(path);
        if (!name) {
          throw new FS.ErrnoError(28);
        }
        if (name === '.' || name === '..') {
          throw new FS.ErrnoError(20);
        }
        var errCode = FS.mayCreate(parent, name);
        if (errCode) {
          throw new FS.ErrnoError(errCode);
        }
        if (!parent.node_ops.mknod) {
          throw new FS.ErrnoError(63);
        }
        return parent.node_ops.mknod(parent, name, mode, dev);
      },
  statfs(path) {
        return FS.statfsNode(FS.lookupPath(path, {follow: true}).node);
      },
  statfsStream(stream) {
        // We keep a separate statfsStream function because noderawfs overrides
        // it. In noderawfs, stream.node is sometimes null. Instead, we need to
        // look at stream.path.
        return FS.statfsNode(stream.node);
      },
  statfsNode(node) {
        // NOTE: None of the defaults here are true. We're just returning safe and
        //       sane values. Currently nodefs and rawfs replace these defaults,
        //       other file systems leave them alone.
        var rtn = {
          bsize: 4096,
          frsize: 4096,
          blocks: 1e6,
          bfree: 5e5,
          bavail: 5e5,
          files: FS.nextInode,
          ffree: FS.nextInode - 1,
          fsid: 42,
          flags: 2,
          namelen: 255,
        };
  
        if (node.node_ops.statfs) {
          Object.assign(rtn, node.node_ops.statfs(node.mount.opts.root));
        }
        return rtn;
      },
  create(path, mode = 0o666) {
        mode &= 4095;
        mode |= 32768;
        return FS.mknod(path, mode, 0);
      },
  mkdir(path, mode = 0o777) {
        mode &= 511 | 512;
        mode |= 16384;
        return FS.mknod(path, mode, 0);
      },
  mkdirTree(path, mode) {
        var dirs = path.split('/');
        var d = '';
        for (var dir of dirs) {
          if (!dir) continue;
          if (d || PATH.isAbs(path)) d += '/';
          d += dir;
          try {
            FS.mkdir(d, mode);
          } catch(e) {
            if (e.errno != 20) throw e;
          }
        }
      },
  mkdev(path, mode, dev) {
        if (typeof dev == 'undefined') {
          dev = mode;
          mode = 0o666;
        }
        mode |= 8192;
        return FS.mknod(path, mode, dev);
      },
  symlink(oldpath, newpath) {
        if (!PATH_FS.resolve(oldpath)) {
          throw new FS.ErrnoError(44);
        }
        var lookup = FS.lookupPath(newpath, { parent: true });
        var parent = lookup.node;
        if (!parent) {
          throw new FS.ErrnoError(44);
        }
        var newname = PATH.basename(newpath);
        var errCode = FS.mayCreate(parent, newname);
        if (errCode) {
          throw new FS.ErrnoError(errCode);
        }
        if (!parent.node_ops.symlink) {
          throw new FS.ErrnoError(63);
        }
        return parent.node_ops.symlink(parent, newname, oldpath);
      },
  rename(old_path, new_path) {
        var old_dirname = PATH.dirname(old_path);
        var new_dirname = PATH.dirname(new_path);
        var old_name = PATH.basename(old_path);
        var new_name = PATH.basename(new_path);
        // parents must exist
        var lookup, old_dir, new_dir;
  
        // let the errors from non existent directories percolate up
        lookup = FS.lookupPath(old_path, { parent: true });
        old_dir = lookup.node;
        lookup = FS.lookupPath(new_path, { parent: true });
        new_dir = lookup.node;
  
        if (!old_dir || !new_dir) throw new FS.ErrnoError(44);
        // need to be part of the same mount
        if (old_dir.mount !== new_dir.mount) {
          throw new FS.ErrnoError(75);
        }
        // source must exist
        var old_node = FS.lookupNode(old_dir, old_name);
        // old path should not be an ancestor of the new path
        var relative = PATH_FS.relative(old_path, new_dirname);
        if (relative.charAt(0) !== '.') {
          throw new FS.ErrnoError(28);
        }
        // new path should not be an ancestor of the old path
        relative = PATH_FS.relative(new_path, old_dirname);
        if (relative.charAt(0) !== '.') {
          throw new FS.ErrnoError(55);
        }
        // see if the new path already exists
        var new_node;
        try {
          new_node = FS.lookupNode(new_dir, new_name);
        } catch (e) {
          // not fatal
        }
        // early out if nothing needs to change
        if (old_node === new_node) {
          return;
        }
        // we'll need to delete the old entry
        var isdir = FS.isDir(old_node.mode);
        var errCode = FS.mayDelete(old_dir, old_name, isdir);
        if (errCode) {
          throw new FS.ErrnoError(errCode);
        }
        // need delete permissions if we'll be overwriting.
        // need create permissions if new doesn't already exist.
        errCode = new_node ?
          FS.mayDelete(new_dir, new_name, isdir) :
          FS.mayCreate(new_dir, new_name);
        if (errCode) {
          throw new FS.ErrnoError(errCode);
        }
        if (!old_dir.node_ops.rename) {
          throw new FS.ErrnoError(63);
        }
        if (FS.isMountpoint(old_node) || (new_node && FS.isMountpoint(new_node))) {
          throw new FS.ErrnoError(10);
        }
        // if we are going to change the parent, check write permissions
        if (new_dir !== old_dir) {
          errCode = FS.nodePermissions(old_dir, 'w');
          if (errCode) {
            throw new FS.ErrnoError(errCode);
          }
        }
        // remove the node from the lookup hash
        FS.hashRemoveNode(old_node);
        // do the underlying fs rename
        try {
          old_dir.node_ops.rename(old_node, new_dir, new_name);
          // update old node (we do this here to avoid each backend
          // needing to)
          old_node.parent = new_dir;
        } catch (e) {
          throw e;
        } finally {
          // add the node back to the hash (in case node_ops.rename
          // changed its name)
          FS.hashAddNode(old_node);
        }
      },
  rmdir(path) {
        var lookup = FS.lookupPath(path, { parent: true });
        var parent = lookup.node;
        var name = PATH.basename(path);
        var node = FS.lookupNode(parent, name);
        var errCode = FS.mayDelete(parent, name, true);
        if (errCode) {
          throw new FS.ErrnoError(errCode);
        }
        if (!parent.node_ops.rmdir) {
          throw new FS.ErrnoError(63);
        }
        if (FS.isMountpoint(node)) {
          throw new FS.ErrnoError(10);
        }
        parent.node_ops.rmdir(parent, name);
        FS.destroyNode(node);
      },
  readdir(path) {
        var lookup = FS.lookupPath(path, { follow: true });
        var node = lookup.node;
        var readdir = FS.checkOpExists(node.node_ops.readdir, 54);
        return readdir(node);
      },
  unlink(path) {
        var lookup = FS.lookupPath(path, { parent: true });
        var parent = lookup.node;
        if (!parent) {
          throw new FS.ErrnoError(44);
        }
        var name = PATH.basename(path);
        var node = FS.lookupNode(parent, name);
        var errCode = FS.mayDelete(parent, name, false);
        if (errCode) {
          // According to POSIX, we should map EISDIR to EPERM, but
          // we instead do what Linux does (and we must, as we use
          // the musl linux libc).
          throw new FS.ErrnoError(errCode);
        }
        if (!parent.node_ops.unlink) {
          throw new FS.ErrnoError(63);
        }
        if (FS.isMountpoint(node)) {
          throw new FS.ErrnoError(10);
        }
        parent.node_ops.unlink(parent, name);
        FS.destroyNode(node);
      },
  readlink(path) {
        var lookup = FS.lookupPath(path);
        var link = lookup.node;
        if (!link) {
          throw new FS.ErrnoError(44);
        }
        if (!link.node_ops.readlink) {
          throw new FS.ErrnoError(28);
        }
        return link.node_ops.readlink(link);
      },
  stat(path, dontFollow) {
        var lookup = FS.lookupPath(path, { follow: !dontFollow });
        var node = lookup.node;
        var getattr = FS.checkOpExists(node.node_ops.getattr, 63);
        return getattr(node);
      },
  fstat(fd) {
        var stream = FS.getStreamChecked(fd);
        var node = stream.node;
        var getattr = stream.stream_ops.getattr;
        var arg = getattr ? stream : node;
        getattr ??= node.node_ops.getattr;
        FS.checkOpExists(getattr, 63)
        return getattr(arg);
      },
  lstat(path) {
        return FS.stat(path, true);
      },
  doChmod(stream, node, mode, dontFollow) {
        FS.doSetAttr(stream, node, {
          mode: (mode & 4095) | (node.mode & ~4095),
          ctime: Date.now(),
          dontFollow
        });
      },
  chmod(path, mode, dontFollow) {
        var node;
        if (typeof path == 'string') {
          var lookup = FS.lookupPath(path, { follow: !dontFollow });
          node = lookup.node;
        } else {
          node = path;
        }
        FS.doChmod(null, node, mode, dontFollow);
      },
  lchmod(path, mode) {
        FS.chmod(path, mode, true);
      },
  fchmod(fd, mode) {
        var stream = FS.getStreamChecked(fd);
        FS.doChmod(stream, stream.node, mode, false);
      },
  doChown(stream, node, dontFollow) {
        FS.doSetAttr(stream, node, {
          timestamp: Date.now(),
          dontFollow
          // we ignore the uid / gid for now
        });
      },
  chown(path, uid, gid, dontFollow) {
        var node;
        if (typeof path == 'string') {
          var lookup = FS.lookupPath(path, { follow: !dontFollow });
          node = lookup.node;
        } else {
          node = path;
        }
        FS.doChown(null, node, dontFollow);
      },
  lchown(path, uid, gid) {
        FS.chown(path, uid, gid, true);
      },
  fchown(fd, uid, gid) {
        var stream = FS.getStreamChecked(fd);
        FS.doChown(stream, stream.node, false);
      },
  doTruncate(stream, node, len) {
        if (FS.isDir(node.mode)) {
          throw new FS.ErrnoError(31);
        }
        if (!FS.isFile(node.mode)) {
          throw new FS.ErrnoError(28);
        }
        var errCode = FS.nodePermissions(node, 'w');
        if (errCode) {
          throw new FS.ErrnoError(errCode);
        }
        FS.doSetAttr(stream, node, {
          size: len,
          timestamp: Date.now()
        });
      },
  truncate(path, len) {
        if (len < 0) {
          throw new FS.ErrnoError(28);
        }
        var node;
        if (typeof path == 'string') {
          var lookup = FS.lookupPath(path, { follow: true });
          node = lookup.node;
        } else {
          node = path;
        }
        FS.doTruncate(null, node, len);
      },
  ftruncate(fd, len) {
        var stream = FS.getStreamChecked(fd);
        if (len < 0 || (stream.flags & 2097155) === 0) {
          throw new FS.ErrnoError(28);
        }
        FS.doTruncate(stream, stream.node, len);
      },
  utime(path, atime, mtime) {
        var lookup = FS.lookupPath(path, { follow: true });
        var node = lookup.node;
        var setattr = FS.checkOpExists(node.node_ops.setattr, 63);
        setattr(node, {
          atime: atime,
          mtime: mtime
        });
      },
  open(path, flags, mode = 0o666) {
        if (path === "") {
          throw new FS.ErrnoError(44);
        }
        flags = typeof flags == 'string' ? FS_modeStringToFlags(flags) : flags;
        if ((flags & 64)) {
          mode = (mode & 4095) | 32768;
        } else {
          mode = 0;
        }
        var node;
        var isDirPath;
        if (typeof path == 'object') {
          node = path;
        } else {
          isDirPath = path.endsWith("/");
          // noent_okay makes it so that if the final component of the path
          // doesn't exist, lookupPath returns `node: undefined`. `path` will be
          // updated to point to the target of all symlinks.
          var lookup = FS.lookupPath(path, {
            follow: !(flags & 131072),
            noent_okay: true
          });
          node = lookup.node;
          path = lookup.path;
        }
        // perhaps we need to create the node
        var created = false;
        if ((flags & 64)) {
          if (node) {
            // if O_CREAT and O_EXCL are set, error out if the node already exists
            if ((flags & 128)) {
              throw new FS.ErrnoError(20);
            }
          } else if (isDirPath) {
            throw new FS.ErrnoError(31);
          } else {
            // node doesn't exist, try to create it
            // Ignore the permission bits here to ensure we can `open` this new
            // file below. We use chmod below the apply the permissions once the
            // file is open.
            node = FS.mknod(path, mode | 0o777, 0);
            created = true;
          }
        }
        if (!node) {
          throw new FS.ErrnoError(44);
        }
        // can't truncate a device
        if (FS.isChrdev(node.mode)) {
          flags &= ~512;
        }
        // if asked only for a directory, then this must be one
        if ((flags & 65536) && !FS.isDir(node.mode)) {
          throw new FS.ErrnoError(54);
        }
        // check permissions, if this is not a file we just created now (it is ok to
        // create and write to a file with read-only permissions; it is read-only
        // for later use)
        if (!created) {
          var errCode = FS.mayOpen(node, flags);
          if (errCode) {
            throw new FS.ErrnoError(errCode);
          }
        }
        // do truncation if necessary
        if ((flags & 512) && !created) {
          FS.truncate(node, 0);
        }
        // we've already handled these, don't pass down to the underlying vfs
        flags &= ~(128 | 512 | 131072);
  
        // register the stream with the filesystem
        var stream = FS.createStream({
          node,
          path: FS.getPath(node),  // we want the absolute path to the node
          flags,
          seekable: true,
          position: 0,
          stream_ops: node.stream_ops,
          // used by the file family libc calls (fopen, fwrite, ferror, etc.)
          ungotten: [],
          error: false
        });
        // call the new stream's open function
        if (stream.stream_ops.open) {
          stream.stream_ops.open(stream);
        }
        if (created) {
          FS.chmod(node, mode & 0o777);
        }
        if (Module['logReadFiles'] && !(flags & 1)) {
          if (!(path in FS.readFiles)) {
            FS.readFiles[path] = 1;
          }
        }
        return stream;
      },
  close(stream) {
        if (FS.isClosed(stream)) {
          throw new FS.ErrnoError(8);
        }
        if (stream.getdents) stream.getdents = null; // free readdir state
        try {
          if (stream.stream_ops.close) {
            stream.stream_ops.close(stream);
          }
        } catch (e) {
          throw e;
        } finally {
          FS.closeStream(stream.fd);
        }
        stream.fd = null;
      },
  isClosed(stream) {
        return stream.fd === null;
      },
  llseek(stream, offset, whence) {
        if (FS.isClosed(stream)) {
          throw new FS.ErrnoError(8);
        }
        if (!stream.seekable || !stream.stream_ops.llseek) {
          throw new FS.ErrnoError(70);
        }
        if (whence != 0 && whence != 1 && whence != 2) {
          throw new FS.ErrnoError(28);
        }
        stream.position = stream.stream_ops.llseek(stream, offset, whence);
        stream.ungotten = [];
        return stream.position;
      },
  read(stream, buffer, offset, length, position) {
        assert(offset >= 0);
        if (length < 0 || position < 0) {
          throw new FS.ErrnoError(28);
        }
        if (FS.isClosed(stream)) {
          throw new FS.ErrnoError(8);
        }
        if ((stream.flags & 2097155) === 1) {
          throw new FS.ErrnoError(8);
        }
        if (FS.isDir(stream.node.mode)) {
          throw new FS.ErrnoError(31);
        }
        if (!stream.stream_ops.read) {
          throw new FS.ErrnoError(28);
        }
        var seeking = typeof position != 'undefined';
        if (!seeking) {
          position = stream.position;
        } else if (!stream.seekable) {
          throw new FS.ErrnoError(70);
        }
        var bytesRead = stream.stream_ops.read(stream, buffer, offset, length, position);
        if (!seeking) stream.position += bytesRead;
        return bytesRead;
      },
  write(stream, buffer, offset, length, position, canOwn) {
        assert(offset >= 0);
        if (length < 0 || position < 0) {
          throw new FS.ErrnoError(28);
        }
        if (FS.isClosed(stream)) {
          throw new FS.ErrnoError(8);
        }
        if ((stream.flags & 2097155) === 0) {
          throw new FS.ErrnoError(8);
        }
        if (FS.isDir(stream.node.mode)) {
          throw new FS.ErrnoError(31);
        }
        if (!stream.stream_ops.write) {
          throw new FS.ErrnoError(28);
        }
        if (stream.seekable && stream.flags & 1024) {
          // seek to the end before writing in append mode
          FS.llseek(stream, 0, 2);
        }
        var seeking = typeof position != 'undefined';
        if (!seeking) {
          position = stream.position;
        } else if (!stream.seekable) {
          throw new FS.ErrnoError(70);
        }
        var bytesWritten = stream.stream_ops.write(stream, buffer, offset, length, position, canOwn);
        if (!seeking) stream.position += bytesWritten;
        return bytesWritten;
      },
  mmap(stream, length, position, prot, flags) {
        // User requests writing to file (prot & PROT_WRITE != 0).
        // Checking if we have permissions to write to the file unless
        // MAP_PRIVATE flag is set. According to POSIX spec it is possible
        // to write to file opened in read-only mode with MAP_PRIVATE flag,
        // as all modifications will be visible only in the memory of
        // the current process.
        if ((prot & 2) !== 0
            && (flags & 2) === 0
            && (stream.flags & 2097155) !== 2) {
          throw new FS.ErrnoError(2);
        }
        if ((stream.flags & 2097155) === 1) {
          throw new FS.ErrnoError(2);
        }
        if (!stream.stream_ops.mmap) {
          throw new FS.ErrnoError(43);
        }
        if (!length) {
          throw new FS.ErrnoError(28);
        }
        return stream.stream_ops.mmap(stream, length, position, prot, flags);
      },
  msync(stream, buffer, offset, length, mmapFlags) {
        assert(offset >= 0);
        if (!stream.stream_ops.msync) {
          return 0;
        }
        return stream.stream_ops.msync(stream, buffer, offset, length, mmapFlags);
      },
  ioctl(stream, cmd, arg) {
        if (!stream.stream_ops.ioctl) {
          throw new FS.ErrnoError(59);
        }
        return stream.stream_ops.ioctl(stream, cmd, arg);
      },
  readFile(path, opts = {}) {
        opts.flags = opts.flags || 0;
        opts.encoding = opts.encoding || 'binary';
        if (opts.encoding !== 'utf8' && opts.encoding !== 'binary') {
          throw new Error(`Invalid encoding type "${opts.encoding}"`);
        }
        var ret;
        var stream = FS.open(path, opts.flags);
        var stat = FS.stat(path);
        var length = stat.size;
        var buf = new Uint8Array(length);
        FS.read(stream, buf, 0, length, 0);
        if (opts.encoding === 'utf8') {
          ret = UTF8ArrayToString(buf);
        } else if (opts.encoding === 'binary') {
          ret = buf;
        }
        FS.close(stream);
        return ret;
      },
  writeFile(path, data, opts = {}) {
        opts.flags = opts.flags || 577;
        var stream = FS.open(path, opts.flags, opts.mode);
        if (typeof data == 'string') {
          var buf = new Uint8Array(lengthBytesUTF8(data)+1);
          var actualNumBytes = stringToUTF8Array(data, buf, 0, buf.length);
          FS.write(stream, buf, 0, actualNumBytes, undefined, opts.canOwn);
        } else if (ArrayBuffer.isView(data)) {
          FS.write(stream, data, 0, data.byteLength, undefined, opts.canOwn);
        } else {
          throw new Error('Unsupported data type');
        }
        FS.close(stream);
      },
  cwd:() => FS.currentPath,
  chdir(path) {
        var lookup = FS.lookupPath(path, { follow: true });
        if (lookup.node === null) {
          throw new FS.ErrnoError(44);
        }
        if (!FS.isDir(lookup.node.mode)) {
          throw new FS.ErrnoError(54);
        }
        var errCode = FS.nodePermissions(lookup.node, 'x');
        if (errCode) {
          throw new FS.ErrnoError(errCode);
        }
        FS.currentPath = lookup.path;
      },
  createDefaultDirectories() {
        FS.mkdir('/tmp');
        FS.mkdir('/home');
        FS.mkdir('/home/web_user');
      },
  createDefaultDevices() {
        // create /dev
        FS.mkdir('/dev');
        // setup /dev/null
        FS.registerDevice(FS.makedev(1, 3), {
          read: () => 0,
          write: (stream, buffer, offset, length, pos) => length,
          llseek: () => 0,
        });
        FS.mkdev('/dev/null', FS.makedev(1, 3));
        // setup /dev/tty and /dev/tty1
        // stderr needs to print output using err() rather than out()
        // so we register a second tty just for it.
        TTY.register(FS.makedev(5, 0), TTY.default_tty_ops);
        TTY.register(FS.makedev(6, 0), TTY.default_tty1_ops);
        FS.mkdev('/dev/tty', FS.makedev(5, 0));
        FS.mkdev('/dev/tty1', FS.makedev(6, 0));
        // setup /dev/[u]random
        // use a buffer to avoid overhead of individual crypto calls per byte
        var randomBuffer = new Uint8Array(1024), randomLeft = 0;
        var randomByte = () => {
          if (randomLeft === 0) {
            randomFill(randomBuffer);
            randomLeft = randomBuffer.byteLength;
          }
          return randomBuffer[--randomLeft];
        };
        FS.createDevice('/dev', 'random', randomByte);
        FS.createDevice('/dev', 'urandom', randomByte);
        // we're not going to emulate the actual shm device,
        // just create the tmp dirs that reside in it commonly
        FS.mkdir('/dev/shm');
        FS.mkdir('/dev/shm/tmp');
      },
  createSpecialDirectories() {
        // create /proc/self/fd which allows /proc/self/fd/6 => readlink gives the
        // name of the stream for fd 6 (see test_unistd_ttyname)
        FS.mkdir('/proc');
        var proc_self = FS.mkdir('/proc/self');
        FS.mkdir('/proc/self/fd');
        FS.mount({
          mount() {
            var node = FS.createNode(proc_self, 'fd', 16895, 73);
            node.stream_ops = {
              llseek: MEMFS.stream_ops.llseek,
            };
            node.node_ops = {
              lookup(parent, name) {
                var fd = +name;
                var stream = FS.getStreamChecked(fd);
                var ret = {
                  parent: null,
                  mount: { mountpoint: 'fake' },
                  node_ops: { readlink: () => stream.path },
                  id: fd + 1,
                };
                ret.parent = ret; // make it look like a simple root node
                return ret;
              },
              readdir() {
                return Array.from(FS.streams.entries())
                  .filter(([k, v]) => v)
                  .map(([k, v]) => k.toString());
              }
            };
            return node;
          }
        }, {}, '/proc/self/fd');
      },
  createStandardStreams(input, output, error) {
        // TODO deprecate the old functionality of a single
        // input / output callback and that utilizes FS.createDevice
        // and instead require a unique set of stream ops
  
        // by default, we symlink the standard streams to the
        // default tty devices. however, if the standard streams
        // have been overwritten we create a unique device for
        // them instead.
        if (input) {
          FS.createDevice('/dev', 'stdin', input);
        } else {
          FS.symlink('/dev/tty', '/dev/stdin');
        }
        if (output) {
          FS.createDevice('/dev', 'stdout', null, output);
        } else {
          FS.symlink('/dev/tty', '/dev/stdout');
        }
        if (error) {
          FS.createDevice('/dev', 'stderr', null, error);
        } else {
          FS.symlink('/dev/tty1', '/dev/stderr');
        }
  
        // open default streams for the stdin, stdout and stderr devices
        var stdin = FS.open('/dev/stdin', 0);
        var stdout = FS.open('/dev/stdout', 1);
        var stderr = FS.open('/dev/stderr', 1);
        assert(stdin.fd === 0, `invalid handle for stdin (${stdin.fd})`);
        assert(stdout.fd === 1, `invalid handle for stdout (${stdout.fd})`);
        assert(stderr.fd === 2, `invalid handle for stderr (${stderr.fd})`);
      },
  staticInit() {
        FS.nameTable = new Array(4096);
  
        FS.mount(MEMFS, {}, '/');
  
        FS.createDefaultDirectories();
        FS.createDefaultDevices();
        FS.createSpecialDirectories();
  
        FS.filesystems = {
          'MEMFS': MEMFS,
        };
      },
  init(input, output, error) {
        assert(!FS.initialized, 'FS.init was previously called. If you want to initialize later with custom parameters, remove any earlier calls (note that one is automatically added to the generated code)');
        FS.initialized = true;
  
        // Allow Module.stdin etc. to provide defaults, if none explicitly passed to us here
        input ??= Module['stdin'];
        output ??= Module['stdout'];
        error ??= Module['stderr'];
  
        FS.createStandardStreams(input, output, error);
      },
  quit() {
        FS.initialized = false;
        // force-flush all streams, so we get musl std streams printed out
        _fflush(0);
        // close all of our streams
        for (var stream of FS.streams) {
          if (stream) {
            FS.close(stream);
          }
        }
      },
  findObject(path, dontResolveLastLink) {
        var ret = FS.analyzePath(path, dontResolveLastLink);
        if (!ret.exists) {
          return null;
        }
        return ret.object;
      },
  analyzePath(path, dontResolveLastLink) {
        // operate from within the context of the symlink's target
        try {
          var lookup = FS.lookupPath(path, { follow: !dontResolveLastLink });
          path = lookup.path;
        } catch (e) {
        }
        var ret = {
          isRoot: false, exists: false, error: 0, name: null, path: null, object: null,
          parentExists: false, parentPath: null, parentObject: null
        };
        try {
          var lookup = FS.lookupPath(path, { parent: true });
          ret.parentExists = true;
          ret.parentPath = lookup.path;
          ret.parentObject = lookup.node;
          ret.name = PATH.basename(path);
          lookup = FS.lookupPath(path, { follow: !dontResolveLastLink });
          ret.exists = true;
          ret.path = lookup.path;
          ret.object = lookup.node;
          ret.name = lookup.node.name;
          ret.isRoot = lookup.path === '/';
        } catch (e) {
          ret.error = e.errno;
        };
        return ret;
      },
  createPath(parent, path, canRead, canWrite) {
        parent = typeof parent == 'string' ? parent : FS.getPath(parent);
        var parts = path.split('/').reverse();
        while (parts.length) {
          var part = parts.pop();
          if (!part) continue;
          var current = PATH.join2(parent, part);
          try {
            FS.mkdir(current);
          } catch (e) {
            if (e.errno != 20) throw e;
          }
          parent = current;
        }
        return current;
      },
  createFile(parent, name, properties, canRead, canWrite) {
        var path = PATH.join2(typeof parent == 'string' ? parent : FS.getPath(parent), name);
        var mode = FS_getMode(canRead, canWrite);
        return FS.create(path, mode);
      },
  createDataFile(parent, name, data, canRead, canWrite, canOwn) {
        var path = name;
        if (parent) {
          parent = typeof parent == 'string' ? parent : FS.getPath(parent);
          path = name ? PATH.join2(parent, name) : parent;
        }
        var mode = FS_getMode(canRead, canWrite);
        var node = FS.create(path, mode);
        if (data) {
          if (typeof data == 'string') {
            var arr = new Array(data.length);
            for (var i = 0, len = data.length; i < len; ++i) arr[i] = data.charCodeAt(i);
            data = arr;
          }
          // make sure we can write to the file
          FS.chmod(node, mode | 146);
          var stream = FS.open(node, 577);
          FS.write(stream, data, 0, data.length, 0, canOwn);
          FS.close(stream);
          FS.chmod(node, mode);
        }
      },
  createDevice(parent, name, input, output) {
        var path = PATH.join2(typeof parent == 'string' ? parent : FS.getPath(parent), name);
        var mode = FS_getMode(!!input, !!output);
        FS.createDevice.major ??= 64;
        var dev = FS.makedev(FS.createDevice.major++, 0);
        // Create a fake device that a set of stream ops to emulate
        // the old behavior.
        FS.registerDevice(dev, {
          open(stream) {
            stream.seekable = false;
          },
          close(stream) {
            // flush any pending line data
            if (output?.buffer?.length) {
              output(10);
            }
          },
          read(stream, buffer, offset, length, pos /* ignored */) {
            var bytesRead = 0;
            for (var i = 0; i < length; i++) {
              var result;
              try {
                result = input();
              } catch (e) {
                throw new FS.ErrnoError(29);
              }
              if (result === undefined && bytesRead === 0) {
                throw new FS.ErrnoError(6);
              }
              if (result === null || result === undefined) break;
              bytesRead++;
              buffer[offset+i] = result;
            }
            if (bytesRead) {
              stream.node.atime = Date.now();
            }
            return bytesRead;
          },
          write(stream, buffer, offset, length, pos) {
            for (var i = 0; i < length; i++) {
              try {
                output(buffer[offset+i]);
              } catch (e) {
                throw new FS.ErrnoError(29);
              }
            }
            if (length) {
              stream.node.mtime = stream.node.ctime = Date.now();
            }
            return i;
          }
        });
        return FS.mkdev(path, mode, dev);
      },
  forceLoadFile(obj) {
        if (obj.isDevice || obj.isFolder || obj.link || obj.contents) return true;
        if (typeof XMLHttpRequest != 'undefined') {
          throw new Error("Lazy loading should have been performed (contents set) in createLazyFile, but it was not. Lazy loading only works in web workers. Use --embed-file or --preload-file in emcc on the main thread.");
        } else { // Command-line.
          try {
            obj.contents = readBinary(obj.url);
            obj.usedBytes = obj.contents.length;
          } catch (e) {
            throw new FS.ErrnoError(29);
          }
        }
      },
  createLazyFile(parent, name, url, canRead, canWrite) {
        // Lazy chunked Uint8Array (implements get and length from Uint8Array).
        // Actual getting is abstracted away for eventual reuse.
        class LazyUint8Array {
          lengthKnown = false;
          chunks = []; // Loaded chunks. Index is the chunk number
          get(idx) {
            if (idx > this.length-1 || idx < 0) {
              return undefined;
            }
            var chunkOffset = idx % this.chunkSize;
            var chunkNum = (idx / this.chunkSize)|0;
            return this.getter(chunkNum)[chunkOffset];
          }
          setDataGetter(getter) {
            this.getter = getter;
          }
          cacheLength() {
            // Find length
            var xhr = new XMLHttpRequest();
            xhr.open('HEAD', url, false);
            xhr.send(null);
            if (!(xhr.status >= 200 && xhr.status < 300 || xhr.status === 304)) throw new Error("Couldn't load " + url + ". Status: " + xhr.status);
            var datalength = Number(xhr.getResponseHeader("Content-length"));
            var header;
            var hasByteServing = (header = xhr.getResponseHeader("Accept-Ranges")) && header === "bytes";
            var usesGzip = (header = xhr.getResponseHeader("Content-Encoding")) && header === "gzip";
  
            var chunkSize = 1024*1024; // Chunk size in bytes
  
            if (!hasByteServing) chunkSize = datalength;
  
            // Function to get a range from the remote URL.
            var doXHR = (from, to) => {
              if (from > to) throw new Error("invalid range (" + from + ", " + to + ") or no bytes requested!");
              if (to > datalength-1) throw new Error("only " + datalength + " bytes available! programmer error!");
  
              // TODO: Use mozResponseArrayBuffer, responseStream, etc. if available.
              var xhr = new XMLHttpRequest();
              xhr.open('GET', url, false);
              if (datalength !== chunkSize) xhr.setRequestHeader("Range", "bytes=" + from + "-" + to);
  
              // Some hints to the browser that we want binary data.
              xhr.responseType = 'arraybuffer';
              if (xhr.overrideMimeType) {
                xhr.overrideMimeType('text/plain; charset=x-user-defined');
              }
  
              xhr.send(null);
              if (!(xhr.status >= 200 && xhr.status < 300 || xhr.status === 304)) throw new Error("Couldn't load " + url + ". Status: " + xhr.status);
              if (xhr.response !== undefined) {
                return new Uint8Array(/** @type{Array<number>} */(xhr.response || []));
              }
              return intArrayFromString(xhr.responseText || '', true);
            };
            var lazyArray = this;
            lazyArray.setDataGetter((chunkNum) => {
              var start = chunkNum * chunkSize;
              var end = (chunkNum+1) * chunkSize - 1; // including this byte
              end = Math.min(end, datalength-1); // if datalength-1 is selected, this is the last block
              if (typeof lazyArray.chunks[chunkNum] == 'undefined') {
                lazyArray.chunks[chunkNum] = doXHR(start, end);
              }
              if (typeof lazyArray.chunks[chunkNum] == 'undefined') throw new Error('doXHR failed!');
              return lazyArray.chunks[chunkNum];
            });
  
            if (usesGzip || !datalength) {
              // if the server uses gzip or doesn't supply the length, we have to download the whole file to get the (uncompressed) length
              chunkSize = datalength = 1; // this will force getter(0)/doXHR do download the whole file
              datalength = this.getter(0).length;
              chunkSize = datalength;
              out("LazyFiles on gzip forces download of the whole file when length is accessed");
            }
  
            this._length = datalength;
            this._chunkSize = chunkSize;
            this.lengthKnown = true;
          }
          get length() {
            if (!this.lengthKnown) {
              this.cacheLength();
            }
            return this._length;
          }
          get chunkSize() {
            if (!this.lengthKnown) {
              this.cacheLength();
            }
            return this._chunkSize;
          }
        }
  
        if (typeof XMLHttpRequest != 'undefined') {
          if (!ENVIRONMENT_IS_WORKER) throw 'Cannot do synchronous binary XHRs outside webworkers in modern browsers. Use --embed-file or --preload-file in emcc';
          var lazyArray = new LazyUint8Array();
          var properties = { isDevice: false, contents: lazyArray };
        } else {
          var properties = { isDevice: false, url: url };
        }
  
        var node = FS.createFile(parent, name, properties, canRead, canWrite);
        // This is a total hack, but I want to get this lazy file code out of the
        // core of MEMFS. If we want to keep this lazy file concept I feel it should
        // be its own thin LAZYFS proxying calls to MEMFS.
        if (properties.contents) {
          node.contents = properties.contents;
        } else if (properties.url) {
          node.contents = null;
          node.url = properties.url;
        }
        // Add a function that defers querying the file size until it is asked the first time.
        Object.defineProperties(node, {
          usedBytes: {
            get: function() { return this.contents.length; }
          }
        });
        // override each stream op with one that tries to force load the lazy file first
        var stream_ops = {};
        var keys = Object.keys(node.stream_ops);
        keys.forEach((key) => {
          var fn = node.stream_ops[key];
          stream_ops[key] = (...args) => {
            FS.forceLoadFile(node);
            return fn(...args);
          };
        });
        function writeChunks(stream, buffer, offset, length, position) {
          var contents = stream.node.contents;
          if (position >= contents.length)
            return 0;
          var size = Math.min(contents.length - position, length);
          assert(size >= 0);
          if (contents.slice) { // normal array
            for (var i = 0; i < size; i++) {
              buffer[offset + i] = contents[position + i];
            }
          } else {
            for (var i = 0; i < size; i++) { // LazyUint8Array from sync binary XHR
              buffer[offset + i] = contents.get(position + i);
            }
          }
          return size;
        }
        // use a custom read function
        stream_ops.read = (stream, buffer, offset, length, position) => {
          FS.forceLoadFile(node);
          return writeChunks(stream, buffer, offset, length, position)
        };
        // use a custom mmap function
        stream_ops.mmap = (stream, length, position, prot, flags) => {
          FS.forceLoadFile(node);
          var ptr = mmapAlloc(length);
          if (!ptr) {
            throw new FS.ErrnoError(48);
          }
          writeChunks(stream, HEAP8, ptr, length, position);
          return { ptr, allocated: true };
        };
        node.stream_ops = stream_ops;
        return node;
      },
  absolutePath() {
        abort('FS.absolutePath has been removed; use PATH_FS.resolve instead');
      },
  createFolder() {
        abort('FS.createFolder has been removed; use FS.mkdir instead');
      },
  createLink() {
        abort('FS.createLink has been removed; use FS.symlink instead');
      },
  joinPath() {
        abort('FS.joinPath has been removed; use PATH.join instead');
      },
  mmapAlloc() {
        abort('FS.mmapAlloc has been replaced by the top level function mmapAlloc');
      },
  standardizePath() {
        abort('FS.standardizePath has been removed; use PATH.normalize instead');
      },
  };
  
  var SYSCALLS = {
  DEFAULT_POLLMASK:5,
  calculateAt(dirfd, path, allowEmpty) {
        if (PATH.isAbs(path)) {
          return path;
        }
        // relative path
        var dir;
        if (dirfd === -100) {
          dir = FS.cwd();
        } else {
          var dirstream = SYSCALLS.getStreamFromFD(dirfd);
          dir = dirstream.path;
        }
        if (path.length == 0) {
          if (!allowEmpty) {
            throw new FS.ErrnoError(44);;
          }
          return dir;
        }
        return dir + '/' + path;
      },
  writeStat(buf, stat) {
        HEAP32[((buf)>>2)] = stat.dev;
        HEAP32[(((buf)+(4))>>2)] = stat.mode;
        HEAPU32[(((buf)+(8))>>2)] = stat.nlink;
        HEAP32[(((buf)+(12))>>2)] = stat.uid;
        HEAP32[(((buf)+(16))>>2)] = stat.gid;
        HEAP32[(((buf)+(20))>>2)] = stat.rdev;
        HEAP64[(((buf)+(24))>>3)] = BigInt(stat.size);
        HEAP32[(((buf)+(32))>>2)] = 4096;
        HEAP32[(((buf)+(36))>>2)] = stat.blocks;
        var atime = stat.atime.getTime();
        var mtime = stat.mtime.getTime();
        var ctime = stat.ctime.getTime();
        HEAP64[(((buf)+(40))>>3)] = BigInt(Math.floor(atime / 1000));
        HEAPU32[(((buf)+(48))>>2)] = (atime % 1000) * 1000 * 1000;
        HEAP64[(((buf)+(56))>>3)] = BigInt(Math.floor(mtime / 1000));
        HEAPU32[(((buf)+(64))>>2)] = (mtime % 1000) * 1000 * 1000;
        HEAP64[(((buf)+(72))>>3)] = BigInt(Math.floor(ctime / 1000));
        HEAPU32[(((buf)+(80))>>2)] = (ctime % 1000) * 1000 * 1000;
        HEAP64[(((buf)+(88))>>3)] = BigInt(stat.ino);
        return 0;
      },
  writeStatFs(buf, stats) {
        HEAP32[(((buf)+(4))>>2)] = stats.bsize;
        HEAP32[(((buf)+(40))>>2)] = stats.bsize;
        HEAP32[(((buf)+(8))>>2)] = stats.blocks;
        HEAP32[(((buf)+(12))>>2)] = stats.bfree;
        HEAP32[(((buf)+(16))>>2)] = stats.bavail;
        HEAP32[(((buf)+(20))>>2)] = stats.files;
        HEAP32[(((buf)+(24))>>2)] = stats.ffree;
        HEAP32[(((buf)+(28))>>2)] = stats.fsid;
        HEAP32[(((buf)+(44))>>2)] = stats.flags;  // ST_NOSUID
        HEAP32[(((buf)+(36))>>2)] = stats.namelen;
      },
  doMsync(addr, stream, len, flags, offset) {
        if (!FS.isFile(stream.node.mode)) {
          throw new FS.ErrnoError(43);
        }
        if (flags & 2) {
          // MAP_PRIVATE calls need not to be synced back to underlying fs
          return 0;
        }
        var buffer = HEAPU8.slice(addr, addr + len);
        FS.msync(stream, buffer, offset, len, flags);
      },
  getStreamFromFD(fd) {
        var stream = FS.getStreamChecked(fd);
        return stream;
      },
  varargs:undefined,
  getStr(ptr) {
        var ret = UTF8ToString(ptr);
        return ret;
      },
  };
  function ___syscall_fcntl64(fd, cmd, varargs) {
  SYSCALLS.varargs = varargs;
  try {
  
      var stream = SYSCALLS.getStreamFromFD(fd);
      switch (cmd) {
        case 0: {
          var arg = syscallGetVarargI();
          if (arg < 0) {
            return -28;
          }
          while (FS.streams[arg]) {
            arg++;
          }
          var newStream;
          newStream = FS.dupStream(stream, arg);
          return newStream.fd;
        }
        case 1:
        case 2:
          return 0;  // FD_CLOEXEC makes no sense for a single process.
        case 3:
          return stream.flags;
        case 4: {
          var arg = syscallGetVarargI();
          stream.flags |= arg;
          return 0;
        }
        case 12: {
          var arg = syscallGetVarargP();
          var offset = 0;
          // We're always unlocked.
          HEAP16[(((arg)+(offset))>>1)] = 2;
          return 0;
        }
        case 13:
        case 14:
          // Pretend that the locking is successful. These are process-level locks,
          // and Emscripten programs are a single process. If we supported linking a
          // filesystem between programs, we'd need to do more here.
          // See https://github.com/emscripten-core/emscripten/issues/23697
          return 0;
      }
      return -28;
    } catch (e) {
    if (typeof FS == 'undefined' || !(e.name === 'ErrnoError')) throw e;
    return -e.errno;
  }
  }

  
  function ___syscall_ioctl(fd, op, varargs) {
  SYSCALLS.varargs = varargs;
  try {
  
      var stream = SYSCALLS.getStreamFromFD(fd);
      switch (op) {
        case 21509: {
          if (!stream.tty) return -59;
          return 0;
        }
        case 21505: {
          if (!stream.tty) return -59;
          if (stream.tty.ops.ioctl_tcgets) {
            var termios = stream.tty.ops.ioctl_tcgets(stream);
            var argp = syscallGetVarargP();
            HEAP32[((argp)>>2)] = termios.c_iflag || 0;
            HEAP32[(((argp)+(4))>>2)] = termios.c_oflag || 0;
            HEAP32[(((argp)+(8))>>2)] = termios.c_cflag || 0;
            HEAP32[(((argp)+(12))>>2)] = termios.c_lflag || 0;
            for (var i = 0; i < 32; i++) {
              HEAP8[(argp + i)+(17)] = termios.c_cc[i] || 0;
            }
            return 0;
          }
          return 0;
        }
        case 21510:
        case 21511:
        case 21512: {
          if (!stream.tty) return -59;
          return 0; // no-op, not actually adjusting terminal settings
        }
        case 21506:
        case 21507:
        case 21508: {
          if (!stream.tty) return -59;
          if (stream.tty.ops.ioctl_tcsets) {
            var argp = syscallGetVarargP();
            var c_iflag = HEAP32[((argp)>>2)];
            var c_oflag = HEAP32[(((argp)+(4))>>2)];
            var c_cflag = HEAP32[(((argp)+(8))>>2)];
            var c_lflag = HEAP32[(((argp)+(12))>>2)];
            var c_cc = []
            for (var i = 0; i < 32; i++) {
              c_cc.push(HEAP8[(argp + i)+(17)]);
            }
            return stream.tty.ops.ioctl_tcsets(stream.tty, op, { c_iflag, c_oflag, c_cflag, c_lflag, c_cc });
          }
          return 0; // no-op, not actually adjusting terminal settings
        }
        case 21519: {
          if (!stream.tty) return -59;
          var argp = syscallGetVarargP();
          HEAP32[((argp)>>2)] = 0;
          return 0;
        }
        case 21520: {
          if (!stream.tty) return -59;
          return -28; // not supported
        }
        case 21531: {
          var argp = syscallGetVarargP();
          return FS.ioctl(stream, op, argp);
        }
        case 21523: {
          // TODO: in theory we should write to the winsize struct that gets
          // passed in, but for now musl doesn't read anything on it
          if (!stream.tty) return -59;
          if (stream.tty.ops.ioctl_tiocgwinsz) {
            var winsize = stream.tty.ops.ioctl_tiocgwinsz(stream.tty);
            var argp = syscallGetVarargP();
            HEAP16[((argp)>>1)] = winsize[0];
            HEAP16[(((argp)+(2))>>1)] = winsize[1];
          }
          return 0;
        }
        case 21524: {
          // TODO: technically, this ioctl call should change the window size.
          // but, since emscripten doesn't have any concept of a terminal window
          // yet, we'll just silently throw it away as we do TIOCGWINSZ
          if (!stream.tty) return -59;
          return 0;
        }
        case 21515: {
          if (!stream.tty) return -59;
          return 0;
        }
        default: return -28; // not supported
      }
    } catch (e) {
    if (typeof FS == 'undefined' || !(e.name === 'ErrnoError')) throw e;
    return -e.errno;
  }
  }

  
  function ___syscall_openat(dirfd, path, flags, varargs) {
  SYSCALLS.varargs = varargs;
  try {
  
      path = SYSCALLS.getStr(path);
      path = SYSCALLS.calculateAt(dirfd, path);
      var mode = varargs ? syscallGetVarargI() : 0;
      return FS.open(path, flags, mode).fd;
    } catch (e) {
    if (typeof FS == 'undefined' || !(e.name === 'ErrnoError')) throw e;
    return -e.errno;
  }
  }

  var __abort_js = () =>
      abort('native code called abort()');

  var __emscripten_throw_longjmp = () => {
      throw Infinity;
    };

  var getHeapMax = () =>
      // Stay one Wasm page short of 4GB: while e.g. Chrome is able to allocate
      // full 4GB Wasm memories, the size will wrap back to 0 bytes in Wasm side
      // for any code that deals with heap sizes, which would require special
      // casing all heap size related code to treat 0 specially.
      2147483648;
  
  var alignMemory = (size, alignment) => {
      assert(alignment, "alignment argument is required");
      return Math.ceil(size / alignment) * alignment;
    };
  
  var growMemory = (size) => {
      var b = wasmMemory.buffer;
      var pages = ((size - b.byteLength + 65535) / 65536) | 0;
      try {
        // round size grow request up to wasm page size (fixed 64KB per spec)
        wasmMemory.grow(pages); // .grow() takes a delta compared to the previous size
        updateMemoryViews();
        return 1 /*success*/;
      } catch(e) {
        err(`growMemory: Attempted to grow heap from ${b.byteLength} bytes to ${size} bytes, but got error: ${e}`);
      }
      // implicit 0 return to save code size (caller will cast "undefined" into 0
      // anyhow)
    };
  var _emscripten_resize_heap = (requestedSize) => {
      var oldSize = HEAPU8.length;
      // With CAN_ADDRESS_2GB or MEMORY64, pointers are already unsigned.
      requestedSize >>>= 0;
      // With multithreaded builds, races can happen (another thread might increase the size
      // in between), so return a failure, and let the caller retry.
      assert(requestedSize > oldSize);
  
      // Memory resize rules:
      // 1.  Always increase heap size to at least the requested size, rounded up
      //     to next page multiple.
      // 2a. If MEMORY_GROWTH_LINEAR_STEP == -1, excessively resize the heap
      //     geometrically: increase the heap size according to
      //     MEMORY_GROWTH_GEOMETRIC_STEP factor (default +20%), At most
      //     overreserve by MEMORY_GROWTH_GEOMETRIC_CAP bytes (default 96MB).
      // 2b. If MEMORY_GROWTH_LINEAR_STEP != -1, excessively resize the heap
      //     linearly: increase the heap size by at least
      //     MEMORY_GROWTH_LINEAR_STEP bytes.
      // 3.  Max size for the heap is capped at 2048MB-WASM_PAGE_SIZE, or by
      //     MAXIMUM_MEMORY, or by ASAN limit, depending on which is smallest
      // 4.  If we were unable to allocate as much memory, it may be due to
      //     over-eager decision to excessively reserve due to (3) above.
      //     Hence if an allocation fails, cut down on the amount of excess
      //     growth, in an attempt to succeed to perform a smaller allocation.
  
      // A limit is set for how much we can grow. We should not exceed that
      // (the wasm binary specifies it, so if we tried, we'd fail anyhow).
      var maxHeapSize = getHeapMax();
      if (requestedSize > maxHeapSize) {
        err(`Cannot enlarge memory, requested ${requestedSize} bytes, but the limit is ${maxHeapSize} bytes!`);
        return false;
      }
  
      // Loop through potential heap size increases. If we attempt a too eager
      // reservation that fails, cut down on the attempted size and reserve a
      // smaller bump instead. (max 3 times, chosen somewhat arbitrarily)
      for (var cutDown = 1; cutDown <= 4; cutDown *= 2) {
        var overGrownHeapSize = oldSize * (1 + 0.2 / cutDown); // ensure geometric growth
        // but limit overreserving (default to capping at +96MB overgrowth at most)
        overGrownHeapSize = Math.min(overGrownHeapSize, requestedSize + 100663296 );
  
        var newSize = Math.min(maxHeapSize, alignMemory(Math.max(requestedSize, overGrownHeapSize), 65536));
  
        var replacement = growMemory(newSize);
        if (replacement) {
  
          return true;
        }
      }
      err(`Failed to grow the heap from ${oldSize} bytes to ${newSize} bytes, not enough memory!`);
      return false;
    };

  function _fd_close(fd) {
  try {
  
      var stream = SYSCALLS.getStreamFromFD(fd);
      FS.close(stream);
      return 0;
    } catch (e) {
    if (typeof FS == 'undefined' || !(e.name === 'ErrnoError')) throw e;
    return e.errno;
  }
  }

  /** @param {number=} offset */
  var doReadv = (stream, iov, iovcnt, offset) => {
      var ret = 0;
      for (var i = 0; i < iovcnt; i++) {
        var ptr = HEAPU32[((iov)>>2)];
        var len = HEAPU32[(((iov)+(4))>>2)];
        iov += 8;
        var curr = FS.read(stream, HEAP8, ptr, len, offset);
        if (curr < 0) return -1;
        ret += curr;
        if (curr < len) break; // nothing more to read
        if (typeof offset != 'undefined') {
          offset += curr;
        }
      }
      return ret;
    };
  
  function _fd_read(fd, iov, iovcnt, pnum) {
  try {
  
      var stream = SYSCALLS.getStreamFromFD(fd);
      var num = doReadv(stream, iov, iovcnt);
      HEAPU32[((pnum)>>2)] = num;
      return 0;
    } catch (e) {
    if (typeof FS == 'undefined' || !(e.name === 'ErrnoError')) throw e;
    return e.errno;
  }
  }

  
  var INT53_MAX = 9007199254740992;
  
  var INT53_MIN = -9007199254740992;
  var bigintToI53Checked = (num) => (num < INT53_MIN || num > INT53_MAX) ? NaN : Number(num);
  function _fd_seek(fd, offset, whence, newOffset) {
    offset = bigintToI53Checked(offset);
  
  
  try {
  
      if (isNaN(offset)) return 61;
      var stream = SYSCALLS.getStreamFromFD(fd);
      FS.llseek(stream, offset, whence);
      HEAP64[((newOffset)>>3)] = BigInt(stream.position);
      if (stream.getdents && offset === 0 && whence === 0) stream.getdents = null; // reset readdir state
      return 0;
    } catch (e) {
    if (typeof FS == 'undefined' || !(e.name === 'ErrnoError')) throw e;
    return e.errno;
  }
  ;
  }

  /** @param {number=} offset */
  var doWritev = (stream, iov, iovcnt, offset) => {
      var ret = 0;
      for (var i = 0; i < iovcnt; i++) {
        var ptr = HEAPU32[((iov)>>2)];
        var len = HEAPU32[(((iov)+(4))>>2)];
        iov += 8;
        var curr = FS.write(stream, HEAP8, ptr, len, offset);
        if (curr < 0) return -1;
        ret += curr;
        if (curr < len) {
          // No more space to write.
          break;
        }
        if (typeof offset != 'undefined') {
          offset += curr;
        }
      }
      return ret;
    };
  
  function _fd_write(fd, iov, iovcnt, pnum) {
  try {
  
      var stream = SYSCALLS.getStreamFromFD(fd);
      var num = doWritev(stream, iov, iovcnt);
      HEAPU32[((pnum)>>2)] = num;
      return 0;
    } catch (e) {
    if (typeof FS == 'undefined' || !(e.name === 'ErrnoError')) throw e;
    return e.errno;
  }
  }

  var wasmTableMirror = [];
  
  /** @type {WebAssembly.Table} */
  var wasmTable;
  var getWasmTableEntry = (funcPtr) => {
      var func = wasmTableMirror[funcPtr];
      if (!func) {
        /** @suppress {checkTypes} */
        wasmTableMirror[funcPtr] = func = wasmTable.get(funcPtr);
      }
      /** @suppress {checkTypes} */
      assert(wasmTable.get(funcPtr) == func, 'JavaScript-side Wasm function table mirror is out of date!');
      return func;
    };

  var getCFunc = (ident) => {
      var func = Module['_' + ident]; // closure exported function
      assert(func, 'Cannot call unknown function ' + ident + ', make sure it is exported');
      return func;
    };
  
  var writeArrayToMemory = (array, buffer) => {
      assert(array.length >= 0, 'writeArrayToMemory array must have a length (should be an array or typed array)')
      HEAP8.set(array, buffer);
    };
  
  
  var stringToUTF8 = (str, outPtr, maxBytesToWrite) => {
      assert(typeof maxBytesToWrite == 'number', 'stringToUTF8(str, outPtr, maxBytesToWrite) is missing the third parameter that specifies the length of the output buffer!');
      return stringToUTF8Array(str, HEAPU8, outPtr, maxBytesToWrite);
    };
  
  var stackAlloc = (sz) => __emscripten_stack_alloc(sz);
  var stringToUTF8OnStack = (str) => {
      var size = lengthBytesUTF8(str) + 1;
      var ret = stackAlloc(size);
      stringToUTF8(str, ret, size);
      return ret;
    };
  
  
  
  
  
    /**
     * @param {string|null=} returnType
     * @param {Array=} argTypes
     * @param {Arguments|Array=} args
     * @param {Object=} opts
     */
  var ccall = (ident, returnType, argTypes, args, opts) => {
      // For fast lookup of conversion functions
      var toC = {
        'string': (str) => {
          var ret = 0;
          if (str !== null && str !== undefined && str !== 0) { // null string
            ret = stringToUTF8OnStack(str);
          }
          return ret;
        },
        'array': (arr) => {
          var ret = stackAlloc(arr.length);
          writeArrayToMemory(arr, ret);
          return ret;
        }
      };
  
      function convertReturnValue(ret) {
        if (returnType === 'string') {
          return UTF8ToString(ret);
        }
        if (returnType === 'boolean') return Boolean(ret);
        return ret;
      }
  
      var func = getCFunc(ident);
      var cArgs = [];
      var stack = 0;
      assert(returnType !== 'array', 'Return type should not be "array".');
      if (args) {
        for (var i = 0; i < args.length; i++) {
          var converter = toC[argTypes[i]];
          if (converter) {
            if (stack === 0) stack = stackSave();
            cArgs[i] = converter(args[i]);
          } else {
            cArgs[i] = args[i];
          }
        }
      }
      var ret = func(...cArgs);
      function onDone(ret) {
        if (stack !== 0) stackRestore(stack);
        return convertReturnValue(ret);
      }
  
      ret = onDone(ret);
      return ret;
    };

  
    /**
     * @param {string=} returnType
     * @param {Array=} argTypes
     * @param {Object=} opts
     */
  var cwrap = (ident, returnType, argTypes, opts) => {
      return (...args) => ccall(ident, returnType, argTypes, args, opts);
    };






    // Precreate a reverse lookup table from chars
    // "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/" back to
    // bytes to make decoding fast.
    for (var base64ReverseLookup = new Uint8Array(123/*'z'+1*/), i = 25; i >= 0; --i) {
      base64ReverseLookup[48+i] = 52+i; // '0-9'
      base64ReverseLookup[65+i] = i; // 'A-Z'
      base64ReverseLookup[97+i] = 26+i; // 'a-z'
    }
    base64ReverseLookup[43] = 62; // '+'
    base64ReverseLookup[47] = 63; // '/'
  ;

  FS.createPreloadedFile = FS_createPreloadedFile;
  FS.staticInit();;
// End JS library code

// include: postlibrary.js
// This file is included after the automatically-generated JS library code
// but before the wasm module is created.

{

  // Begin ATMODULES hooks
  if (Module['noExitRuntime']) noExitRuntime = Module['noExitRuntime'];
if (Module['preloadPlugins']) preloadPlugins = Module['preloadPlugins'];
if (Module['print']) out = Module['print'];
if (Module['printErr']) err = Module['printErr'];
if (Module['wasmBinary']) wasmBinary = Module['wasmBinary'];
  // End ATMODULES hooks

  checkIncomingModuleAPI();

  if (Module['arguments']) arguments_ = Module['arguments'];
  if (Module['thisProgram']) thisProgram = Module['thisProgram'];

  // Assertions on removed incoming Module JS APIs.
  assert(typeof Module['memoryInitializerPrefixURL'] == 'undefined', 'Module.memoryInitializerPrefixURL option was removed, use Module.locateFile instead');
  assert(typeof Module['pthreadMainPrefixURL'] == 'undefined', 'Module.pthreadMainPrefixURL option was removed, use Module.locateFile instead');
  assert(typeof Module['cdInitializerPrefixURL'] == 'undefined', 'Module.cdInitializerPrefixURL option was removed, use Module.locateFile instead');
  assert(typeof Module['filePackagePrefixURL'] == 'undefined', 'Module.filePackagePrefixURL option was removed, use Module.locateFile instead');
  assert(typeof Module['read'] == 'undefined', 'Module.read option was removed');
  assert(typeof Module['readAsync'] == 'undefined', 'Module.readAsync option was removed (modify readAsync in JS)');
  assert(typeof Module['readBinary'] == 'undefined', 'Module.readBinary option was removed (modify readBinary in JS)');
  assert(typeof Module['setWindowTitle'] == 'undefined', 'Module.setWindowTitle option was removed (modify emscripten_set_window_title in JS)');
  assert(typeof Module['TOTAL_MEMORY'] == 'undefined', 'Module.TOTAL_MEMORY has been renamed Module.INITIAL_MEMORY');
  assert(typeof Module['ENVIRONMENT'] == 'undefined', 'Module.ENVIRONMENT has been deprecated. To force the environment, use the ENVIRONMENT compile-time option (for example, -sENVIRONMENT=web or -sENVIRONMENT=node)');
  assert(typeof Module['STACK_SIZE'] == 'undefined', 'STACK_SIZE can no longer be set at runtime.  Use -sSTACK_SIZE at link time')
  // If memory is defined in wasm, the user can't provide it, or set INITIAL_MEMORY
  assert(typeof Module['wasmMemory'] == 'undefined', 'Use of `wasmMemory` detected.  Use -sIMPORTED_MEMORY to define wasmMemory externally');
  assert(typeof Module['INITIAL_MEMORY'] == 'undefined', 'Detected runtime INITIAL_MEMORY setting.  Use -sIMPORTED_MEMORY to define wasmMemory dynamically');

}

// Begin runtime exports
  Module['ccall'] = ccall;
  Module['cwrap'] = cwrap;
  Module['setValue'] = setValue;
  Module['getValue'] = getValue;
  Module['UTF8ToString'] = UTF8ToString;
  Module['stringToUTF8'] = stringToUTF8;
  Module['lengthBytesUTF8'] = lengthBytesUTF8;
  var missingLibrarySymbols = [
  'writeI53ToI64',
  'writeI53ToI64Clamped',
  'writeI53ToI64Signaling',
  'writeI53ToU64Clamped',
  'writeI53ToU64Signaling',
  'readI53FromI64',
  'readI53FromU64',
  'convertI32PairToI53',
  'convertI32PairToI53Checked',
  'convertU32PairToI53',
  'getTempRet0',
  'setTempRet0',
  'zeroMemory',
  'exitJS',
  'inetPton4',
  'inetNtop4',
  'inetPton6',
  'inetNtop6',
  'readSockaddr',
  'writeSockaddr',
  'emscriptenLog',
  'readEmAsmArgs',
  'jstoi_q',
  'getExecutableName',
  'listenOnce',
  'autoResumeAudioContext',
  'getDynCaller',
  'dynCall',
  'handleException',
  'keepRuntimeAlive',
  'runtimeKeepalivePush',
  'runtimeKeepalivePop',
  'callUserCallback',
  'maybeExit',
  'asmjsMangle',
  'HandleAllocator',
  'getNativeTypeSize',
  'addOnInit',
  'addOnPostCtor',
  'addOnPreMain',
  'addOnExit',
  'STACK_SIZE',
  'STACK_ALIGN',
  'POINTER_SIZE',
  'ASSERTIONS',
  'uleb128Encode',
  'sigToWasmTypes',
  'generateFuncType',
  'convertJsFunctionToWasm',
  'getEmptyTableSlot',
  'updateTableMap',
  'getFunctionAddress',
  'addFunction',
  'removeFunction',
  'reallyNegative',
  'unSign',
  'strLen',
  'reSign',
  'formatString',
  'intArrayToString',
  'AsciiToString',
  'stringToAscii',
  'UTF16ToString',
  'stringToUTF16',
  'lengthBytesUTF16',
  'UTF32ToString',
  'stringToUTF32',
  'lengthBytesUTF32',
  'stringToNewUTF8',
  'registerKeyEventCallback',
  'maybeCStringToJsString',
  'findEventTarget',
  'getBoundingClientRect',
  'fillMouseEventData',
  'registerMouseEventCallback',
  'registerWheelEventCallback',
  'registerUiEventCallback',
  'registerFocusEventCallback',
  'fillDeviceOrientationEventData',
  'registerDeviceOrientationEventCallback',
  'fillDeviceMotionEventData',
  'registerDeviceMotionEventCallback',
  'screenOrientation',
  'fillOrientationChangeEventData',
  'registerOrientationChangeEventCallback',
  'fillFullscreenChangeEventData',
  'registerFullscreenChangeEventCallback',
  'JSEvents_requestFullscreen',
  'JSEvents_resizeCanvasForFullscreen',
  'registerRestoreOldStyle',
  'hideEverythingExceptGivenElement',
  'restoreHiddenElements',
  'setLetterbox',
  'softFullscreenResizeWebGLRenderTarget',
  'doRequestFullscreen',
  'fillPointerlockChangeEventData',
  'registerPointerlockChangeEventCallback',
  'registerPointerlockErrorEventCallback',
  'requestPointerLock',
  'fillVisibilityChangeEventData',
  'registerVisibilityChangeEventCallback',
  'registerTouchEventCallback',
  'fillGamepadEventData',
  'registerGamepadEventCallback',
  'registerBeforeUnloadEventCallback',
  'fillBatteryEventData',
  'battery',
  'registerBatteryEventCallback',
  'setCanvasElementSize',
  'getCanvasElementSize',
  'jsStackTrace',
  'getCallstack',
  'convertPCtoSourceLocation',
  'getEnvStrings',
  'checkWasiClock',
  'wasiRightsToMuslOFlags',
  'wasiOFlagsToMuslOFlags',
  'safeSetTimeout',
  'setImmediateWrapped',
  'safeRequestAnimationFrame',
  'clearImmediateWrapped',
  'registerPostMainLoop',
  'registerPreMainLoop',
  'getPromise',
  'makePromise',
  'idsToPromises',
  'makePromiseCallback',
  'ExceptionInfo',
  'findMatchingCatch',
  'Browser_asyncPrepareDataCounter',
  'isLeapYear',
  'ydayFromDate',
  'arraySum',
  'addDays',
  'getSocketFromFD',
  'getSocketAddress',
  'FS_mkdirTree',
  '_setNetworkCallback',
  'heapObjectForWebGLType',
  'toTypedArrayIndex',
  'webgl_enable_ANGLE_instanced_arrays',
  'webgl_enable_OES_vertex_array_object',
  'webgl_enable_WEBGL_draw_buffers',
  'webgl_enable_WEBGL_multi_draw',
  'webgl_enable_EXT_polygon_offset_clamp',
  'webgl_enable_EXT_clip_control',
  'webgl_enable_WEBGL_polygon_mode',
  'emscriptenWebGLGet',
  'computeUnpackAlignedImageSize',
  'colorChannelsInGlTextureFormat',
  'emscriptenWebGLGetTexPixelData',
  'emscriptenWebGLGetUniform',
  'webglGetUniformLocation',
  'webglPrepareUniformLocationsBeforeFirstUse',
  'webglGetLeftBracePos',
  'emscriptenWebGLGetVertexAttrib',
  '__glGetActiveAttribOrUniform',
  'writeGLArray',
  'registerWebGlEventCallback',
  'runAndAbortIfError',
  'ALLOC_NORMAL',
  'ALLOC_STACK',
  'allocate',
  'writeStringToMemory',
  'writeAsciiToMemory',
  'demangle',
  'stackTrace',
];
missingLibrarySymbols.forEach(missingLibrarySymbol)

  var unexportedSymbols = [
  'run',
  'addRunDependency',
  'removeRunDependency',
  'out',
  'err',
  'callMain',
  'abort',
  'wasmMemory',
  'wasmExports',
  'HEAPF32',
  'HEAPF64',
  'HEAP8',
  'HEAPU8',
  'HEAP16',
  'HEAPU16',
  'HEAP32',
  'HEAPU32',
  'HEAP64',
  'HEAPU64',
  'writeStackCookie',
  'checkStackCookie',
  'INT53_MAX',
  'INT53_MIN',
  'bigintToI53Checked',
  'stackSave',
  'stackRestore',
  'stackAlloc',
  'ptrToString',
  'getHeapMax',
  'growMemory',
  'ENV',
  'ERRNO_CODES',
  'strError',
  'DNS',
  'Protocols',
  'Sockets',
  'timers',
  'warnOnce',
  'readEmAsmArgsArray',
  'asyncLoad',
  'alignMemory',
  'mmapAlloc',
  'wasmTable',
  'noExitRuntime',
  'addOnPreRun',
  'addOnPostRun',
  'freeTableIndexes',
  'functionsInTableMap',
  'PATH',
  'PATH_FS',
  'UTF8Decoder',
  'UTF8ArrayToString',
  'stringToUTF8Array',
  'intArrayFromString',
  'UTF16Decoder',
  'stringToUTF8OnStack',
  'writeArrayToMemory',
  'JSEvents',
  'specialHTMLTargets',
  'findCanvasEventTarget',
  'currentFullscreenStrategy',
  'restoreOldWindowedStyle',
  'UNWIND_CACHE',
  'ExitStatus',
  'doReadv',
  'doWritev',
  'initRandomFill',
  'randomFill',
  'emSetImmediate',
  'emClearImmediate_deps',
  'emClearImmediate',
  'promiseMap',
  'uncaughtExceptionCount',
  'exceptionLast',
  'exceptionCaught',
  'Browser',
  'requestFullscreen',
  'requestFullScreen',
  'setCanvasSize',
  'getUserMedia',
  'createContext',
  'getPreloadedImageData__data',
  'wget',
  'MONTH_DAYS_REGULAR',
  'MONTH_DAYS_LEAP',
  'MONTH_DAYS_REGULAR_CUMULATIVE',
  'MONTH_DAYS_LEAP_CUMULATIVE',
  'base64Decode',
  'SYSCALLS',
  'preloadPlugins',
  'FS_createPreloadedFile',
  'FS_modeStringToFlags',
  'FS_getMode',
  'FS_stdin_getChar_buffer',
  'FS_stdin_getChar',
  'FS_unlink',
  'FS_createPath',
  'FS_createDevice',
  'FS_readFile',
  'FS',
  'FS_root',
  'FS_mounts',
  'FS_devices',
  'FS_streams',
  'FS_nextInode',
  'FS_nameTable',
  'FS_currentPath',
  'FS_initialized',
  'FS_ignorePermissions',
  'FS_filesystems',
  'FS_syncFSRequests',
  'FS_readFiles',
  'FS_lookupPath',
  'FS_getPath',
  'FS_hashName',
  'FS_hashAddNode',
  'FS_hashRemoveNode',
  'FS_lookupNode',
  'FS_createNode',
  'FS_destroyNode',
  'FS_isRoot',
  'FS_isMountpoint',
  'FS_isFile',
  'FS_isDir',
  'FS_isLink',
  'FS_isChrdev',
  'FS_isBlkdev',
  'FS_isFIFO',
  'FS_isSocket',
  'FS_flagsToPermissionString',
  'FS_nodePermissions',
  'FS_mayLookup',
  'FS_mayCreate',
  'FS_mayDelete',
  'FS_mayOpen',
  'FS_checkOpExists',
  'FS_nextfd',
  'FS_getStreamChecked',
  'FS_getStream',
  'FS_createStream',
  'FS_closeStream',
  'FS_dupStream',
  'FS_doSetAttr',
  'FS_chrdev_stream_ops',
  'FS_major',
  'FS_minor',
  'FS_makedev',
  'FS_registerDevice',
  'FS_getDevice',
  'FS_getMounts',
  'FS_syncfs',
  'FS_mount',
  'FS_unmount',
  'FS_lookup',
  'FS_mknod',
  'FS_statfs',
  'FS_statfsStream',
  'FS_statfsNode',
  'FS_create',
  'FS_mkdir',
  'FS_mkdev',
  'FS_symlink',
  'FS_rename',
  'FS_rmdir',
  'FS_readdir',
  'FS_readlink',
  'FS_stat',
  'FS_fstat',
  'FS_lstat',
  'FS_doChmod',
  'FS_chmod',
  'FS_lchmod',
  'FS_fchmod',
  'FS_doChown',
  'FS_chown',
  'FS_lchown',
  'FS_fchown',
  'FS_doTruncate',
  'FS_truncate',
  'FS_ftruncate',
  'FS_utime',
  'FS_open',
  'FS_close',
  'FS_isClosed',
  'FS_llseek',
  'FS_read',
  'FS_write',
  'FS_mmap',
  'FS_msync',
  'FS_ioctl',
  'FS_writeFile',
  'FS_cwd',
  'FS_chdir',
  'FS_createDefaultDirectories',
  'FS_createDefaultDevices',
  'FS_createSpecialDirectories',
  'FS_createStandardStreams',
  'FS_staticInit',
  'FS_init',
  'FS_quit',
  'FS_findObject',
  'FS_analyzePath',
  'FS_createFile',
  'FS_createDataFile',
  'FS_forceLoadFile',
  'FS_createLazyFile',
  'FS_absolutePath',
  'FS_createFolder',
  'FS_createLink',
  'FS_joinPath',
  'FS_mmapAlloc',
  'FS_standardizePath',
  'MEMFS',
  'TTY',
  'PIPEFS',
  'SOCKFS',
  'tempFixedLengthArray',
  'miniTempWebGLFloatBuffers',
  'miniTempWebGLIntBuffers',
  'GL',
  'AL',
  'GLUT',
  'EGL',
  'GLEW',
  'IDBStore',
  'SDL',
  'SDL_gfx',
  'allocateUTF8',
  'allocateUTF8OnStack',
  'print',
  'printErr',
  'jstoi_s',
];
unexportedSymbols.forEach(unexportedRuntimeSymbol);

  // End runtime exports
  // Begin JS library exports
  // End JS library exports

// end include: postlibrary.js

function checkIncomingModuleAPI() {
  ignoredModuleProp('fetchSettings');
}
var wasmImports = {
  /** @export */
  __syscall_fcntl64: ___syscall_fcntl64,
  /** @export */
  __syscall_ioctl: ___syscall_ioctl,
  /** @export */
  __syscall_openat: ___syscall_openat,
  /** @export */
  _abort_js: __abort_js,
  /** @export */
  _emscripten_throw_longjmp: __emscripten_throw_longjmp,
  /** @export */
  emscripten_resize_heap: _emscripten_resize_heap,
  /** @export */
  fd_close: _fd_close,
  /** @export */
  fd_read: _fd_read,
  /** @export */
  fd_seek: _fd_seek,
  /** @export */
  fd_write: _fd_write,
  /** @export */
  invoke_ii,
  /** @export */
  invoke_iiiii
};
var wasmExports = await createWasm();
// Imports from the Wasm binary.
var ___wasm_call_ctors = createExportWrapper('__wasm_call_ctors', 0);
var _mqmqa_R = Module['_mqmqa_R'] = createExportWrapper('mqmqa_R', 0);
var _mqmqa_ideal_entropy_binary = Module['_mqmqa_ideal_entropy_binary'] = createExportWrapper('mqmqa_ideal_entropy_binary', 1);
var _mqmqa_reference_energy = Module['_mqmqa_reference_energy'] = createExportWrapper('mqmqa_reference_energy', 12);
var _mqmqa_ideal_mixing_energy = Module['_mqmqa_ideal_mixing_energy'] = createExportWrapper('mqmqa_ideal_mixing_energy', 15);
var _free = Module['_free'] = createExportWrapper('free', 1);
var _mqmqa_excess_energy = Module['_mqmqa_excess_energy'] = createExportWrapper('mqmqa_excess_energy', 22);
var _mqmqa_coordination = Module['_mqmqa_coordination'] = createExportWrapper('mqmqa_coordination', 16);
var _mqmqa_equilibrate = Module['_mqmqa_equilibrate'] = createExportWrapper('mqmqa_equilibrate', 36);
var _malloc = Module['_malloc'] = createExportWrapper('malloc', 1);
var _mqmqa_db_read_string = Module['_mqmqa_db_read_string'] = createExportWrapper('mqmqa_db_read_string', 1);
var _mqmqa_db_read_file = Module['_mqmqa_db_read_file'] = createExportWrapper('mqmqa_db_read_file', 1);
var _mqmqa_db_free = Module['_mqmqa_db_free'] = createExportWrapper('mqmqa_db_free', 1);
var _mqmqa_db_error = Module['_mqmqa_db_error'] = createExportWrapper('mqmqa_db_error', 0);
var _mqmqa_db_num_elements = Module['_mqmqa_db_num_elements'] = createExportWrapper('mqmqa_db_num_elements', 1);
var _mqmqa_db_element = Module['_mqmqa_db_element'] = createExportWrapper('mqmqa_db_element', 2);
var _mqmqa_db_element_mass = Module['_mqmqa_db_element_mass'] = createExportWrapper('mqmqa_db_element_mass', 2);
var _mqmqa_db_num_phases = Module['_mqmqa_db_num_phases'] = createExportWrapper('mqmqa_db_num_phases', 1);
var _mqmqa_db_phase_index = Module['_mqmqa_db_phase_index'] = createExportWrapper('mqmqa_db_phase_index', 2);
var _mqmqa_db_phase_name = Module['_mqmqa_db_phase_name'] = createExportWrapper('mqmqa_db_phase_name', 2);
var _mqmqa_db_phase_is_subq = Module['_mqmqa_db_phase_is_subq'] = createExportWrapper('mqmqa_db_phase_is_subq', 2);
var _mqmqa_ph_num_cations = Module['_mqmqa_ph_num_cations'] = createExportWrapper('mqmqa_ph_num_cations', 2);
var _mqmqa_ph_num_anions = Module['_mqmqa_ph_num_anions'] = createExportWrapper('mqmqa_ph_num_anions', 2);
var _mqmqa_ph_cation = Module['_mqmqa_ph_cation'] = createExportWrapper('mqmqa_ph_cation', 3);
var _mqmqa_ph_anion = Module['_mqmqa_ph_anion'] = createExportWrapper('mqmqa_ph_anion', 3);
var _mqmqa_ph_cation_charge = Module['_mqmqa_ph_cation_charge'] = createExportWrapper('mqmqa_ph_cation_charge', 3);
var _mqmqa_ph_anion_charge = Module['_mqmqa_ph_anion_charge'] = createExportWrapper('mqmqa_ph_anion_charge', 3);
var _mqmqa_ph_cation_group = Module['_mqmqa_ph_cation_group'] = createExportWrapper('mqmqa_ph_cation_group', 3);
var _mqmqa_ph_anion_group = Module['_mqmqa_ph_anion_group'] = createExportWrapper('mqmqa_ph_anion_group', 3);
var _mqmqa_ph_num_pairs = Module['_mqmqa_ph_num_pairs'] = createExportWrapper('mqmqa_ph_num_pairs', 2);
var _mqmqa_ph_pair_indices = Module['_mqmqa_ph_pair_indices'] = createExportWrapper('mqmqa_ph_pair_indices', 4);
var _mqmqa_ph_pair_stoich = Module['_mqmqa_ph_pair_stoich'] = createExportWrapper('mqmqa_ph_pair_stoich', 3);
var _mqmqa_ph_pair_zeta = Module['_mqmqa_ph_pair_zeta'] = createExportWrapper('mqmqa_ph_pair_zeta', 3);
var _mqmqa_ph_pair_gibbs = Module['_mqmqa_ph_pair_gibbs'] = createExportWrapper('mqmqa_ph_pair_gibbs', 4);
var _mqmqa_ph_num_mqmz = Module['_mqmqa_ph_num_mqmz'] = createExportWrapper('mqmqa_ph_num_mqmz', 2);
var _mqmqa_ph_mqmz = Module['_mqmqa_ph_mqmz'] = createExportWrapper('mqmqa_ph_mqmz', 7);
var _mqmqa_ph_num_mqmx = Module['_mqmqa_ph_num_mqmx'] = createExportWrapper('mqmqa_ph_num_mqmx', 2);
var _mqmqa_ph_mqmx = Module['_mqmqa_ph_mqmx'] = createExportWrapper('mqmqa_ph_mqmx', 10);
var _mqmqa_ph_mqmx_L = Module['_mqmqa_ph_mqmx_L'] = createExportWrapper('mqmqa_ph_mqmx_L', 4);
var _mqmqa_db_phase_kind = Module['_mqmqa_db_phase_kind'] = createExportWrapper('mqmqa_db_phase_kind', 2);
var _mqmqa_ph_cef_num_subl = Module['_mqmqa_ph_cef_num_subl'] = createExportWrapper('mqmqa_ph_cef_num_subl', 2);
var _mqmqa_ph_cef_subl_ncon = Module['_mqmqa_ph_cef_subl_ncon'] = createExportWrapper('mqmqa_ph_cef_subl_ncon', 3);
var _mqmqa_ph_cef_site_ratio = Module['_mqmqa_ph_cef_site_ratio'] = createExportWrapper('mqmqa_ph_cef_site_ratio', 3);
var _mqmqa_ph_cef_num_constituents = Module['_mqmqa_ph_cef_num_constituents'] = createExportWrapper('mqmqa_ph_cef_num_constituents', 2);
var _mqmqa_ph_cef_constituent = Module['_mqmqa_ph_cef_constituent'] = createExportWrapper('mqmqa_ph_cef_constituent', 4);
var _mqmqa_ph_cef_gibbs = Module['_mqmqa_ph_cef_gibbs'] = createExportWrapper('mqmqa_ph_cef_gibbs', 5);
var _mqmqa_cef_gibbs = Module['_mqmqa_cef_gibbs'] = createExportWrapper('mqmqa_cef_gibbs', 18);
var _mqmqa_db_num_stoich = Module['_mqmqa_db_num_stoich'] = createExportWrapper('mqmqa_db_num_stoich', 1);
var _mqmqa_db_stoich_name = Module['_mqmqa_db_stoich_name'] = createExportWrapper('mqmqa_db_stoich_name', 2);
var _mqmqa_db_stoich_gibbs = Module['_mqmqa_db_stoich_gibbs'] = createExportWrapper('mqmqa_db_stoich_gibbs', 3);
var _mqmqa_num_quadruplets = Module['_mqmqa_num_quadruplets'] = createExportWrapper('mqmqa_num_quadruplets', 2);
var _mqmqa_enumerate_quadruplets = Module['_mqmqa_enumerate_quadruplets'] = createExportWrapper('mqmqa_enumerate_quadruplets', 6);
var _fflush = createExportWrapper('fflush', 1);
var _strerror = createExportWrapper('strerror', 1);
var _emscripten_stack_get_end = wasmExports['emscripten_stack_get_end']
var _emscripten_stack_get_base = wasmExports['emscripten_stack_get_base']
var _setThrew = createExportWrapper('setThrew', 2);
var _emscripten_stack_init = wasmExports['emscripten_stack_init']
var _emscripten_stack_get_free = wasmExports['emscripten_stack_get_free']
var __emscripten_stack_restore = wasmExports['_emscripten_stack_restore']
var __emscripten_stack_alloc = wasmExports['_emscripten_stack_alloc']
var _emscripten_stack_get_current = wasmExports['emscripten_stack_get_current']

function invoke_ii(index,a1) {
  var sp = stackSave();
  try {
    return getWasmTableEntry(index)(a1);
  } catch(e) {
    stackRestore(sp);
    if (e !== e+0) throw e;
    _setThrew(1, 0);
  }
}

function invoke_iiiii(index,a1,a2,a3,a4) {
  var sp = stackSave();
  try {
    return getWasmTableEntry(index)(a1,a2,a3,a4);
  } catch(e) {
    stackRestore(sp);
    if (e !== e+0) throw e;
    _setThrew(1, 0);
  }
}


// include: postamble.js
// === Auto-generated postamble setup entry stuff ===

var calledRun;

function stackCheckInit() {
  // This is normally called automatically during __wasm_call_ctors but need to
  // get these values before even running any of the ctors so we call it redundantly
  // here.
  _emscripten_stack_init();
  // TODO(sbc): Move writeStackCookie to native to to avoid this.
  writeStackCookie();
}

function run() {

  if (runDependencies > 0) {
    dependenciesFulfilled = run;
    return;
  }

  stackCheckInit();

  preRun();

  // a preRun added a dependency, run will be called later
  if (runDependencies > 0) {
    dependenciesFulfilled = run;
    return;
  }

  function doRun() {
    // run may have just been called through dependencies being fulfilled just in this very frame,
    // or while the async setStatus time below was happening
    assert(!calledRun);
    calledRun = true;
    Module['calledRun'] = true;

    if (ABORT) return;

    initRuntime();

    readyPromiseResolve(Module);
    Module['onRuntimeInitialized']?.();
    consumedModuleProp('onRuntimeInitialized');

    assert(!Module['_main'], 'compiled without a main, but one is present. if you added it from JS, use Module["onRuntimeInitialized"]');

    postRun();
  }

  if (Module['setStatus']) {
    Module['setStatus']('Running...');
    setTimeout(() => {
      setTimeout(() => Module['setStatus'](''), 1);
      doRun();
    }, 1);
  } else
  {
    doRun();
  }
  checkStackCookie();
}

function checkUnflushedContent() {
  // Compiler settings do not allow exiting the runtime, so flushing
  // the streams is not possible. but in ASSERTIONS mode we check
  // if there was something to flush, and if so tell the user they
  // should request that the runtime be exitable.
  // Normally we would not even include flush() at all, but in ASSERTIONS
  // builds we do so just for this check, and here we see if there is any
  // content to flush, that is, we check if there would have been
  // something a non-ASSERTIONS build would have not seen.
  // How we flush the streams depends on whether we are in SYSCALLS_REQUIRE_FILESYSTEM=0
  // mode (which has its own special function for this; otherwise, all
  // the code is inside libc)
  var oldOut = out;
  var oldErr = err;
  var has = false;
  out = err = (x) => {
    has = true;
  }
  try { // it doesn't matter if it fails
    _fflush(0);
    // also flush in the JS FS layer
    ['stdout', 'stderr'].forEach((name) => {
      var info = FS.analyzePath('/dev/' + name);
      if (!info) return;
      var stream = info.object;
      var rdev = stream.rdev;
      var tty = TTY.ttys[rdev];
      if (tty?.output?.length) {
        has = true;
      }
    });
  } catch(e) {}
  out = oldOut;
  err = oldErr;
  if (has) {
    warnOnce('stdio streams had content in them that was not flushed. you should set EXIT_RUNTIME to 1 (see the Emscripten FAQ), or make sure to emit a newline when you printf etc.');
  }
}

function preInit() {
  if (Module['preInit']) {
    if (typeof Module['preInit'] == 'function') Module['preInit'] = [Module['preInit']];
    while (Module['preInit'].length > 0) {
      Module['preInit'].shift()();
    }
  }
  consumedModuleProp('preInit');
}

preInit();
run();

// end include: postamble.js

// include: postamble_modularize.js
// In MODULARIZE mode we wrap the generated code in a factory function
// and return either the Module itself, or a promise of the module.
//
// We assign to the `moduleRtn` global here and configure closure to see
// this as and extern so it won't get minified.

moduleRtn = readyPromise;

// Assertion for attempting to access module properties on the incoming
// moduleArg.  In the past we used this object as the prototype of the module
// and assigned properties to it, but now we return a distinct object.  This
// keeps the instance private until it is ready (i.e the promise has been
// resolved).
for (const prop of Object.keys(Module)) {
  if (!(prop in moduleArg)) {
    Object.defineProperty(moduleArg, prop, {
      configurable: true,
      get() {
        abort(`Access to module property ('${prop}') is no longer possible via the module constructor argument; Instead, use the result of the module constructor.`)
      }
    });
  }
}
// end include: postamble_modularize.js



  return moduleRtn;
}
);
})();
if (typeof exports === 'object' && typeof module === 'object') {
  module.exports = Hephaestus;
  // This default export looks redundant, but it allows TS to import this
  // commonjs style module.
  module.exports.default = Hephaestus;
} else if (typeof define === 'function' && define['amd'])
  define([], () => Hephaestus);
