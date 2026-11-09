/* summit-gtk-module: small GTK 3 fixes for Summit OS's menu bar.
 *
 * GTK shows the underlined "mnemonic" letters (File, Edit ...) in a window until that window has had
 * keyboard focus once. The menu bar is a panel that never takes focus, so its menus always showed the
 * underlines. In the panel process this module keeps them hidden. Alt shortcuts keep working.
 *
 * Build: gcc -shared -fPIC -O2 -o libsummit-gtk-module.so summit-gtk-module.c $(pkg-config --cflags --libs gtk+-3.0)
 * Install: /usr/lib/x86_64-linux-gnu/gtk-3.0/modules/ and add "summit-gtk-module" to xsettings /Gtk/Modules.
 */
#include <gtk/gtk.h>
#include <string.h>

static void keep_hidden (GtkWindow *w, GParamSpec *p, gpointer d)
{
    if (gtk_window_get_mnemonics_visible (w))
        gtk_window_set_mnemonics_visible (w, FALSE);
}

static void watch (GObject *o)
{
    if (!GTK_IS_WINDOW (o) || g_object_get_data (o, "summit-mnemonics")) return;
    g_object_set_data (o, "summit-mnemonics", GINT_TO_POINTER (1));
    g_signal_connect (o, "notify::mnemonics-visible", G_CALLBACK (keep_hidden), NULL);
    keep_hidden (GTK_WINDOW (o), NULL, NULL);
}

static gboolean on_map (GSignalInvocationHint *ih, guint n, const GValue *params, gpointer d)
{
    GObject *o = g_value_get_object (&params[0]);
    if (GTK_IS_WINDOW (o)) watch (o);
    return TRUE;
}

static gboolean is_panel (void)
{
    const char *p = g_get_prgname ();
    return p && (strcmp (p, "xfce4-panel") == 0 || g_str_has_prefix (p, "wrapper-"));
}

G_MODULE_EXPORT void gtk_module_init (gint *argc, gchar ***argv)
{
    if (!is_panel ()) return;
    g_signal_add_emission_hook (g_signal_lookup ("map", GTK_TYPE_WIDGET), 0, on_map, NULL, NULL);
    GList *wins = gtk_window_list_toplevels ();            /* when loaded into an already running panel */
    for (GList *l = wins; l; l = l->next) watch (l->data);
    g_list_free (wins);
}

G_MODULE_EXPORT const gchar *g_module_check_init (GModule *module)
{
    g_module_make_resident (module);                      /* GTK may unload modules; the hook must stay */
    return NULL;
}
