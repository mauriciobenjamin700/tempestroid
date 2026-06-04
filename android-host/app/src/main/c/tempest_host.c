// JNI shim: initialize and run the embedded CPython interpreter, plus the
// bidirectional bridge (phase B3).
//
// Mirrors the CPython Platforms/Android/testbed `main_activity.c` embedding
// pattern: set PYTHONHOME via PyConfig.home, Py_InitializeFromConfig, Py_RunMain.
// On top of that it registers a built-in `_tempest_host` module so Python can:
//   - send_to_host(json)       Python -> Kotlin (PythonRuntime.onMessageFromPython)
//   - set_event_sink(callable)  register the callback Kotlin invokes per event
// and exposes the JNI entry `dispatchEvent` for Kotlin -> Python.
// This is the official-CPython contract (PEP 738) — no pyjnius/Chaquopy.

#include <jni.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <android/log.h>
#include <Python.h>

#define TAG "tempestroid"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, TAG, __VA_ARGS__)

// Cached at JNI_OnLoad / startPython so both directions can reach the JVM/host.
static JavaVM *g_vm = NULL;
static jclass g_runtime_cls = NULL;       // global ref to PythonRuntime
static jmethodID g_on_msg_mid = NULL;     // onMessageFromPython(String)V

// The Python callable registered by _tempest_host.set_event_sink. Invoked from
// dispatchEvent (the Kotlin/UI thread) under the GIL.
static PyObject *g_event_sink = NULL;

JNIEXPORT jint JNICALL JNI_OnLoad(JavaVM *vm, void *reserved) {
    g_vm = vm;
    return JNI_VERSION_1_6;
}

// --- built-in module: _tempest_host -----------------------------------------

// Python -> Kotlin: hand a serialized message to PythonRuntime.onMessageFromPython.
static PyObject *host_send_to_host(PyObject *self, PyObject *args) {
    const char *message;
    if (!PyArg_ParseTuple(args, "s", &message)) {
        return NULL;
    }
    if (g_runtime_cls == NULL || g_on_msg_mid == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "host class not initialized");
        return NULL;
    }

    // This runs on the interpreter thread (spawned by the JVM, already attached).
    JNIEnv *env = NULL;
    jint rc = (*g_vm)->GetEnv(g_vm, (void **) &env, JNI_VERSION_1_6);
    if (rc == JNI_EDETACHED) {
        if ((*g_vm)->AttachCurrentThread(g_vm, &env, NULL) != JNI_OK) {
            PyErr_SetString(PyExc_RuntimeError, "AttachCurrentThread failed");
            return NULL;
        }
    } else if (rc != JNI_OK) {
        PyErr_SetString(PyExc_RuntimeError, "GetEnv failed");
        return NULL;
    }

    jstring jmsg = (*env)->NewStringUTF(env, message);
    (*env)->CallStaticVoidMethod(env, g_runtime_cls, g_on_msg_mid, jmsg);
    (*env)->DeleteLocalRef(env, jmsg);
    Py_RETURN_NONE;
}

// Register the callback Kotlin will drive on each device event.
static PyObject *host_set_event_sink(PyObject *self, PyObject *args) {
    PyObject *cb;
    if (!PyArg_ParseTuple(args, "O", &cb)) {
        return NULL;
    }
    if (!PyCallable_Check(cb)) {
        PyErr_SetString(PyExc_TypeError, "event sink must be callable");
        return NULL;
    }
    Py_INCREF(cb);
    Py_XDECREF(g_event_sink);
    g_event_sink = cb;
    Py_RETURN_NONE;
}

static PyMethodDef host_methods[] = {
    {"send_to_host", host_send_to_host, METH_VARARGS,
     "Ship a serialized message to the Kotlin host (Python -> host)."},
    {"set_event_sink", host_set_event_sink, METH_VARARGS,
     "Register the callable invoked on each incoming device event."},
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef host_module = {
    PyModuleDef_HEAD_INIT, "_tempest_host", NULL, -1, host_methods,
    NULL, NULL, NULL, NULL,
};

PyMODINIT_FUNC PyInit__tempest_host(void) {
    return PyModule_Create(&host_module);
}

// --- Kotlin -> Python: deliver one event ------------------------------------

JNIEXPORT void JNICALL
Java_org_tempestroid_host_PythonRuntime_dispatchEvent(
        JNIEnv *env, jobject thiz, jstring jToken, jstring jPayload) {
    const char *token = (*env)->GetStringUTFChars(env, jToken, NULL);
    const char *payload = (*env)->GetStringUTFChars(env, jPayload, NULL);

    PyGILState_STATE gil = PyGILState_Ensure();
    if (g_event_sink != NULL) {
        PyObject *r = PyObject_CallFunction(g_event_sink, "ss", token, payload);
        if (r == NULL) {
            PyErr_Print();
        } else {
            Py_DECREF(r);
        }
    } else {
        LOGE("dispatchEvent: no event sink registered yet");
    }
    PyGILState_Release(gil);

    (*env)->ReleaseStringUTFChars(env, jToken, token);
    (*env)->ReleaseStringUTFChars(env, jPayload, payload);
}

// --- interpreter liveness ---------------------------------------------------

// True when a Python interpreter is already initialized in this process. The
// background worker uses it to decide between dispatching into the live
// interpreter (app alive) and booting a fresh one (process woken from dead).
JNIEXPORT jboolean JNICALL
Java_org_tempestroid_host_PythonRuntime_isPythonInitialized(
        JNIEnv *env, jobject thiz) {
    (void)env;
    (void)thiz;
    return Py_IsInitialized() ? JNI_TRUE : JNI_FALSE;
}

// --- interpreter bootstrap ---------------------------------------------------

JNIEXPORT jint JNICALL
Java_org_tempestroid_host_PythonRuntime_startPython(
        JNIEnv *env, jobject thiz, jstring jHome, jobjectArray jArgs) {

    // Android's Signal Catcher blocks SIGUSR1; CPython needs it unblocked.
    sigset_t set;
    sigemptyset(&set);
    sigaddset(&set, SIGUSR1);
    pthread_sigmask(SIG_UNBLOCK, &set, NULL);

    // Cache the host class + method for the Python -> Kotlin direction. The
    // local FindClass ref is promoted to a global so it survives past this call.
    jclass cls = (*env)->FindClass(env, "org/tempestroid/host/PythonRuntime");
    if (cls != NULL) {
        g_runtime_cls = (*env)->NewGlobalRef(env, cls);
        g_on_msg_mid = (*env)->GetStaticMethodID(
            env, cls, "onMessageFromPython", "(Ljava/lang/String;)V");
    }
    if (g_runtime_cls == NULL || g_on_msg_mid == NULL) {
        LOGE("failed to resolve PythonRuntime.onMessageFromPython");
    }

    // The built-in module must be registered BEFORE the interpreter starts.
    if (PyImport_AppendInittab("_tempest_host", PyInit__tempest_host) != 0) {
        LOGE("PyImport_AppendInittab(_tempest_host) failed");
        return -1;
    }

    const char *home = (*env)->GetStringUTFChars(env, jHome, NULL);

    PyStatus status;
    PyConfig config;
    PyConfig_InitPythonConfig(&config);

    // PYTHONHOME is set via config.home (not an env var) in embedded mode.
    status = PyConfig_SetBytesString(&config, &config.home, home);
    if (PyStatus_Exception(status)) goto fail;

    // Build argv (argv[0] left as a placeholder, as in embedded mode).
    jsize argc = (*env)->GetArrayLength(env, jArgs);
    char **argv = (char **) malloc(sizeof(char *) * (argc + 1));
    argv[0] = "";
    for (jsize i = 0; i < argc; i++) {
        jstring s = (jstring) (*env)->GetObjectArrayElement(env, jArgs, i);
        argv[i + 1] = strdup((*env)->GetStringUTFChars(env, s, NULL));
    }
    status = PyConfig_SetBytesArgv(&config, argc + 1, argv);
    if (PyStatus_Exception(status)) goto fail;

    LOGI("Py_InitializeFromConfig (home=%s)", home);
    status = Py_InitializeFromConfig(&config);
    if (PyStatus_Exception(status)) goto fail;
    PyConfig_Clear(&config);

    // TODO(B2): redirect stdout/stderr to logcat via pipes + pump threads
    // (testbed's redirectStdioToLogcat technique).

    int rc = Py_RunMain();
    (*env)->ReleaseStringUTFChars(env, jHome, home);
    return rc;

fail:
    LOGE("python init failed: %s", status.err_msg ? status.err_msg : "?");
    PyConfig_Clear(&config);
    (*env)->ReleaseStringUTFChars(env, jHome, home);
    return -1;
}
