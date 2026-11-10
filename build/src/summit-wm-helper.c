/* summit-wm-helper: macOS-style full screen for Summit OS.
 *
 *  - The green button (maximize) makes a window full screen: it covers the whole display, menu bar and dock
 *    included. Windows that open already maximized (an app restoring its last size) are left as they are.
 *  - In full screen, pushing the pointer against the top edge asks summit-shell to slide down a bar with the
 *    window's traffic lights (close, minimize, leave full screen).
 *
 * Event driven: it sleeps until a window changes, and only watches the pointer (a cheap query, ~8 times a
 * second) while a full-screen window is active. Turn the full-screen behaviour off by creating
 * ~/.config/summit/classic-maximize.
 *
 * Build: gcc -O2 -Wall -o summit-wm-helper summit-wm-helper.c -lX11
 */
#include <X11/Xlib.h>
#include <X11/Xatom.h>
#include <X11/Xutil.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <time.h>
#include <sys/select.h>

#define MAXW 1024
static Display *dpy; static Window root;
static Atom A_CLIENTS, A_STATE, A_MAXV, A_MAXH, A_FULL, A_ACTIVE, A_TYPE, A_NORMAL, A_HIDDEN;
static struct { Window w; double seen; int maxed; } known[MAXW]; static int nknown;

static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec / 1e9; }
static int quiet_err(Display *d, XErrorEvent *e) { (void)d; (void)e; return 0; }   /* windows vanish all the time */

static int get_atoms(Window w, Atom prop, Atom *out, int max) {
    Atom type; int fmt; unsigned long n = 0, after; unsigned char *data = NULL;
    if (XGetWindowProperty(dpy, w, prop, 0, max, False, XA_ATOM, &type, &fmt, &n, &after, &data) != Success || !data) return 0;
    if (n > (unsigned long)max) n = max;
    memcpy(out, data, n * sizeof(Atom)); XFree(data); return (int)n;
}
static int has(Atom *a, int n, Atom x) { for (int i = 0; i < n; i++) if (a[i] == x) return 1; return 0; }

static Window get_window(Window w, Atom prop) {
    Atom type; int fmt; unsigned long n = 0, after; unsigned char *data = NULL; Window r = 0;
    if (XGetWindowProperty(dpy, w, prop, 0, 1, False, XA_WINDOW, &type, &fmt, &n, &after, &data) == Success && data) {
        if (n) r = *(Window *)data;
        XFree(data);
    }
    return r;
}

static int idx(Window w) { for (int i = 0; i < nknown; i++) if (known[i].w == w) return i; return -1; }

static int is_normal(Window w) {
    Atom t[8]; int n = get_atoms(w, A_TYPE, t, 8);
    return n == 0 || has(t, n, A_NORMAL);
}

static void send_state(Window w, long action, Atom a1, Atom a2) {
    XEvent e; memset(&e, 0, sizeof e);
    e.xclient.type = ClientMessage; e.xclient.window = w; e.xclient.message_type = A_STATE; e.xclient.format = 32;
    e.xclient.data.l[0] = action; e.xclient.data.l[1] = (long)a1; e.xclient.data.l[2] = (long)a2; e.xclient.data.l[3] = 1;
    XSendEvent(dpy, root, False, SubstructureRedirectMask | SubstructureNotifyMask, &e);
}

static int classic(void) {
    char p[512]; const char *h = getenv("HOME");
    snprintf(p, sizeof p, "%s/.config/summit/classic-maximize", h ? h : "");
    return access(p, F_OK) == 0;
}

static void sync_clients(void) {
    Atom type; int fmt; unsigned long n = 0, after; unsigned char *data = NULL;
    if (XGetWindowProperty(dpy, root, A_CLIENTS, 0, MAXW, False, XA_WINDOW, &type, &fmt, &n, &after, &data) != Success || !data) return;
    Window *ws = (Window *)data;
    for (unsigned long i = 0; i < n && nknown < MAXW; i++) {
        if (idx(ws[i]) >= 0) continue;
        Atom st[16]; int ns = get_atoms(ws[i], A_STATE, st, 16);
        known[nknown].w = ws[i]; known[nknown].seen = now();
        known[nknown].maxed = has(st, ns, A_MAXV) && has(st, ns, A_MAXH);    /* opened maximized: leave it */
        nknown++;
        XSelectInput(dpy, ws[i], PropertyChangeMask);
    }
    /* forget closed windows */
    for (int i = 0; i < nknown; ) {
        int alive = 0;
        for (unsigned long j = 0; j < n; j++) if (ws[j] == known[i].w) { alive = 1; break; }
        if (!alive) known[i] = known[--nknown]; else i++;
    }
    XFree(data);
}

static void state_changed(Window w) {
    int i = idx(w); if (i < 0) return;
    Atom st[16]; int n = get_atoms(w, A_STATE, st, 16);
    int maxed = has(st, n, A_MAXV) && has(st, n, A_MAXH);
    if (maxed && !known[i].maxed && !has(st, n, A_FULL) && !has(st, n, A_HIDDEN)
        && now() - known[i].seen > 1.5 && is_normal(w) && !classic()) {
        /* green button: full screen instead (leaving maximize first, so "exit full screen" restores the old size) */
        send_state(w, 0, A_MAXV, A_MAXH);
        send_state(w, 1, A_FULL, 0);
        XFlush(dpy);
    }
    known[i].maxed = maxed;
}

static int active_is_fullscreen(Window *out) {
    Window a = get_window(root, A_ACTIVE); if (!a) return 0;
    Atom st[16]; int n = get_atoms(a, A_STATE, st, 16);
    *out = a; return has(st, n, A_FULL);
}

static void reveal(Window w) {
    char arg[64]; snprintf(arg, sizeof arg, "[<'0x%lx'>]", (unsigned long)w);
    if (fork() == 0) {
        execlp("gdbus", "gdbus", "call", "--session", "--dest", "org.summitos.Shell", "--object-path", "/org/summitos/Shell",
               "--method", "org.gtk.Actions.Activate", "fullscreen-bar", arg, "{}", (char *)NULL);
        _exit(1);
    }
}

int main(void) {
    signal(SIGCHLD, SIG_IGN);
    if (!(dpy = XOpenDisplay(NULL))) { fprintf(stderr, "summit-wm-helper: no display\n"); return 1; }
    XSetErrorHandler(quiet_err);
    root = DefaultRootWindow(dpy);
    A_CLIENTS = XInternAtom(dpy, "_NET_CLIENT_LIST", False); A_STATE = XInternAtom(dpy, "_NET_WM_STATE", False);
    A_MAXV = XInternAtom(dpy, "_NET_WM_STATE_MAXIMIZED_VERT", False); A_MAXH = XInternAtom(dpy, "_NET_WM_STATE_MAXIMIZED_HORZ", False);
    A_FULL = XInternAtom(dpy, "_NET_WM_STATE_FULLSCREEN", False); A_HIDDEN = XInternAtom(dpy, "_NET_WM_STATE_HIDDEN", False);
    A_ACTIVE = XInternAtom(dpy, "_NET_ACTIVE_WINDOW", False); A_TYPE = XInternAtom(dpy, "_NET_WM_WINDOW_TYPE", False);
    A_NORMAL = XInternAtom(dpy, "_NET_WM_WINDOW_TYPE_NORMAL", False);
    XSelectInput(dpy, root, PropertyChangeMask);
    sync_clients();

    int fd = ConnectionNumber(dpy); double edge_since = 0; int armed = 1;
    for (;;) {
        while (XPending(dpy)) {
            XEvent e; XNextEvent(dpy, &e);
            if (e.type != PropertyNotify) continue;
            if (e.xproperty.window == root && e.xproperty.atom == A_CLIENTS) sync_clients();
            else if (e.xproperty.atom == A_STATE) state_changed(e.xproperty.window);
        }
        Window fw = 0; int full = active_is_fullscreen(&fw);
        XFlush(dpy);
        if (XEventsQueued(dpy, QueuedAlready)) continue;   /* events read in while asking: handle them before sleeping */
        fd_set fds; FD_ZERO(&fds); FD_SET(fd, &fds);
        struct timeval tv = { 0, 120000 };
        if (!full) { edge_since = 0; armed = 1; select(fd + 1, &fds, NULL, NULL, NULL); continue; }   /* sleep until something happens */
        select(fd + 1, &fds, NULL, NULL, &tv);
        Window r, c; int rx, ry, wx, wy; unsigned int m;
        if (!XQueryPointer(dpy, root, &r, &c, &rx, &ry, &wx, &wy, &m)) continue;
        if (ry <= 1 && !m) {                       /* resting against the top edge (not dragging) */
            if (!edge_since) edge_since = now();
            if (armed && now() - edge_since > 0.25) { reveal(fw); armed = 0; }
        } else {
            edge_since = 0;
            if (ry > 60) armed = 1;                /* ready again once the pointer has moved away */
        }
    }
}
