using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace DicomViewer.AnatomyLab
{
    public enum NameLanguage { Italian, English, Latin }

    /// <summary>One structure of the modelled body as the names table has it (model_names.json).</summary>
    [Serializable]
    public class NameEntry
    {
        public string key;        // the mesh's name
        public string layer;      // skin, fat, muscles, skeleton, organs
        public string la, en, it; // its name in Latin, English, Italian
        public string from;       // where its shape comes from: a key of the table's "sources"
        public bool drawn;        // not read from this body
        public string note;       // a key of the table's "notes", or empty
    }

    [Serializable]
    public class NameText
    {
        public string key, la, en, it;
    }

    [Serializable]
    public class NameTable
    {
        public NameText[] layers, sources, notes;
        public NameEntry[] structures;
    }

    /// <summary>
    /// The names of the modelled body's structures in Italian, English and Latin, and what a student is told
    /// about where each shape comes from. Read when the body starts from
    /// StreamingAssets/anatomy/model_names.json, which backend/tools/anatomy_model/names.py writes when the model
    /// is built; then from model_names_corrections.json beside it, if there is one: a teacher's corrections (the
    /// same shape; only "structures" with "key" and the names to change), which a rebuild does not touch.
    /// </summary>
    public sealed class ModelNames
    {
        public const string Folder = "anatomy", File = "model_names.json", Corrections = "model_names_corrections.json";

        private readonly Dictionary<string, NameEntry> byKey = new Dictionary<string, NameEntry>();
        private readonly Dictionary<string, NameText> layers = new Dictionary<string, NameText>(), sources = new Dictionary<string, NameText>(),
                                                      notes = new Dictionary<string, NameText>();

        public int Count => byKey.Count;
        /// <summary>How many of a corrections file's entries were taken (for the log).</summary>
        public int Corrected { get; private set; }

        /// <summary>The table from the app's own folder; empty (every Find null) where there is no file.</summary>
        public static ModelNames Load()
        {
            string dir = Path.Combine(Application.streamingAssetsPath, Folder);
            string main = Path.Combine(dir, File), fixes = Path.Combine(dir, Corrections);
            try
            {
                return Parse(System.IO.File.Exists(main) ? System.IO.File.ReadAllText(main) : null, System.IO.File.Exists(fixes) ? System.IO.File.ReadAllText(fixes) : null);
            }
            catch (Exception e)
            {
                Debug.LogWarning($"ModelNames: {main} could not be read ({e.Message}): structures are shown by their mesh names");
                return new ModelNames();
            }
        }

        /// <summary>The table from its JSON text, and a corrections file's text after it (either may be null).</summary>
        public static ModelNames Parse(string json, string corrections = null)
        {
            var names = new ModelNames();
            if (!string.IsNullOrEmpty(json))
            {
                NameTable t = JsonUtility.FromJson<NameTable>(json);
                if (t != null)
                {
                    foreach (NameEntry e in t.structures ?? new NameEntry[0]) if (!string.IsNullOrEmpty(e.key)) names.byKey[e.key] = e;
                    foreach (NameText x in t.layers ?? new NameText[0]) names.layers[x.key] = x;
                    foreach (NameText x in t.sources ?? new NameText[0]) names.sources[x.key] = x;
                    foreach (NameText x in t.notes ?? new NameText[0]) names.notes[x.key] = x;
                }
            }
            if (!string.IsNullOrEmpty(corrections))
            {
                NameTable t = JsonUtility.FromJson<NameTable>(corrections);
                foreach (NameEntry fix in t?.structures ?? new NameEntry[0])
                {
                    if (string.IsNullOrEmpty(fix.key) || !names.byKey.TryGetValue(fix.key, out NameEntry e)) continue;
                    if (!string.IsNullOrEmpty(fix.la)) e.la = fix.la;
                    if (!string.IsNullOrEmpty(fix.en)) e.en = fix.en;
                    if (!string.IsNullOrEmpty(fix.it)) e.it = fix.it;
                    names.Corrected++;
                }
            }
            return names;
        }

        /// <summary>The structure whose mesh has this name; null where the table does not have it.</summary>
        public NameEntry Find(string key) => key != null && byKey.TryGetValue(key, out NameEntry e) ? e : null;

        public static string In(NameLanguage language, string la, string en, string it)
        {
            string wanted = language == NameLanguage.Latin ? la : language == NameLanguage.English ? en : it;
            return !string.IsNullOrEmpty(wanted) ? wanted : !string.IsNullOrEmpty(en) ? en : !string.IsNullOrEmpty(it) ? it : la;
        }

        /// <summary>A structure's name in a language (its English where that language has none).</summary>
        public string Name(NameEntry e, NameLanguage language) => e == null ? "" : In(language, e.la, e.en, e.it);

        /// <summary>A layer's name in a language; the key itself where the table does not have it.</summary>
        public string Layer(string key, NameLanguage language) => key != null && layers.TryGetValue(key, out NameText t) ? In(language, t.la, t.en, t.it) : key ?? "";

        /// <summary>What a student is told about where the structure's shape comes from (the table has it in
        /// English and Italian; with Latin names the card speaks Italian).</summary>
        public string Source(NameEntry e, NameLanguage language) => Text(sources, e?.from, language);

        public string Note(NameEntry e, NameLanguage language) => Text(notes, e?.note, language);

        private static string Text(Dictionary<string, NameText> table, string key, NameLanguage language)
        {
            if (string.IsNullOrEmpty(key) || !table.TryGetValue(key, out NameText t)) return "";
            return language == NameLanguage.English ? t.en : t.it;
        }
    }
}
