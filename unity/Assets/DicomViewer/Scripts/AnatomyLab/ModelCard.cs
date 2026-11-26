using System.Collections.Generic;
using UnityEngine;

namespace DicomViewer.AnatomyLab
{
    /// <summary>
    /// The card that names the structure a student has touched: its name large in the language chosen, the other
    /// two languages under it, its layer, and where its shape comes from (in amber when it is drawn and not read
    /// from this body). It is made of meshes that ride with the camera, a panel and lines of text a few
    /// centimetres before the lens, laid out in screen pixels: so the camera draws it itself, on the screen and
    /// in the pictures ModelSnapshot takes alike (what OnGUI draws is in no picture).
    /// </summary>
    public sealed class ModelCard
    {
        public const float Width = 440f, Pad = 16f, Margin = 14f, Top = 70f;       // pixels at scale 1
        public static readonly Color Panel = new Color(0.07f, 0.08f, 0.10f, 0.86f);
        public static readonly Color TitleColour = Color.white, Other = new Color(0.78f, 0.82f, 0.88f), Faint = new Color(0.62f, 0.66f, 0.72f),
                                     Amber = new Color(1f, 0.74f, 0.30f);

        /// <summary>One line of the card as it is laid out (for tests and for the log).</summary>
        public struct Line
        {
            public string text;
            public float size;       // font pixels at scale 1
            public Color colour;
            public float gapAbove;   // pixels at scale 1
        }

        private GameObject root;
        private MeshRenderer panel;
        private Material panelMaterial;
        private Font font;
        private readonly List<TextMesh> texts = new List<TextMesh>();
        private float height;
        private float scale = 1f;

        public bool Shown => root != null && root.activeSelf;

        /// <summary>How high the card is on the screen, in pixels; 0 while it is put away. (What is laid out under
        /// it, the button that takes the named structure off, starts there.)</summary>
        public float PixelHeight => Shown ? height : 0f;
        /// <summary>The lines last shown, wrapped.</summary>
        public List<Line> Lines { get; } = new List<Line>();

        /// <summary>What the card says of a structure: its lines, not yet wrapped. `entry` null: the mesh's own
        /// name alone (a structure the table does not have).</summary>
        public static List<Line> Compose(ModelNames names, NameEntry entry, string meshName, NameLanguage language)
        {
            var lines = new List<Line>();
            if (entry == null || names == null)
            {
                lines.Add(new Line { text = meshName, size = 26f, colour = TitleColour });
                return lines;
            }
            lines.Add(new Line { text = names.Name(entry, language), size = 26f, colour = TitleColour });
            foreach (NameLanguage other in new[] { NameLanguage.Latin, NameLanguage.Italian, NameLanguage.English })
            {
                if (other == language) continue;
                string tag = other == NameLanguage.Latin ? "LA" : other == NameLanguage.Italian ? "IT" : "EN";
                lines.Add(new Line { text = tag + "   " + names.Name(entry, other), size = 16f, colour = Other, gapAbove = lines.Count == 1 ? 8f : 2f });
            }
            // The card's own words are English or Italian (with Latin names: Italian), and the layer's name with them.
            NameLanguage spoken = language == NameLanguage.English ? NameLanguage.English : NameLanguage.Italian;
            lines.Add(new Line { text = (spoken == NameLanguage.English ? "Layer" : "Strato") + ": " + names.Layer(entry.layer, spoken), size = 15f, colour = Faint, gapAbove = 10f });
            string source = names.Source(entry, language);
            if (!string.IsNullOrEmpty(source)) lines.Add(new Line { text = source, size = 15f, colour = entry.drawn ? Amber : Faint, gapAbove = 4f });
            string note = names.Note(entry, language);
            if (!string.IsNullOrEmpty(note)) lines.Add(new Line { text = note, size = 15f, colour = Faint, gapAbove = 4f });
            return lines;
        }

        /// <summary>A text broken into lines no wider than `width` pixels at this font size (at the words' spaces;
        /// a word longer than the line stays whole).</summary>
        public static List<string> Wrap(Font font, string text, int size, float width)
        {
            var lines = new List<string>();
            if (string.IsNullOrEmpty(text)) return lines;
            if (font != null) font.RequestCharactersInTexture(text, size, FontStyle.Normal);
            float Wide(string s)
            {
                if (font == null) return s.Length * size * 0.5f;
                float w = 0f;
                foreach (char c in s) w += font.GetCharacterInfo(c, out CharacterInfo info, size, FontStyle.Normal) ? info.advance : size * 0.5f;
                return w;
            }
            string line = "";
            foreach (string word in text.Split(' '))
            {
                string longer = line.Length == 0 ? word : line + " " + word;
                if (line.Length > 0 && Wide(longer) > width) { lines.Add(line); line = word; }
                else line = longer;
            }
            if (line.Length > 0) lines.Add(line);
            return lines;
        }

        /// <summary>Shows the card with these lines (wrapped to its width) before this camera.</summary>
        public void Show(Camera cam, List<Line> lines)
        {
            if (cam == null) return;
            Build(cam);
            scale = Mathf.Max(1f, Screen.dpi > 0f ? Screen.dpi / 96f : 1f);
            Lines.Clear();
            foreach (Line l in lines)
            {
                bool first = true;
                foreach (string part in Wrap(font, l.text, Mathf.RoundToInt(l.size * scale), (Width - 2f * Pad) * scale))
                {
                    Lines.Add(new Line { text = part, size = l.size, colour = l.colour, gapAbove = first ? l.gapAbove : 0f });
                    first = false;
                }
            }
            float y = Pad * scale;
            for (int i = 0; i < Lines.Count; i++)
            {
                Line l = Lines[i];
                TextMesh t = i < texts.Count ? texts[i] : NewText();
                int px = Mathf.RoundToInt(l.size * scale);
                y += l.gapAbove * scale;
                t.gameObject.SetActive(true);
                t.text = l.text;
                t.fontSize = px;
                t.characterSize = 10f;                               // a glyph's pixel is then one of the card's units (TextMesh: 0.1 per pixel at 1)
                t.color = l.colour;
                t.transform.localPosition = new Vector3(Pad * scale, -y, 0f);
                y += px * 1.22f;
            }
            for (int i = Lines.Count; i < texts.Count; i++) texts[i].gameObject.SetActive(false);
            height = y + Pad * scale;
            panel.transform.localPosition = new Vector3(Width * scale * 0.5f, -height * 0.5f, 0.001f);
            panel.transform.localScale = new Vector3(Width * scale, height, 1f);
            root.SetActive(true);
            Place(cam);
        }

        public void Hide()
        {
            if (root != null) root.SetActive(false);
        }

        /// <summary>Keeps the card at the right of the camera's picture, under the buttons, whatever the picture's
        /// size: call when the camera or the screen may have changed (every frame).</summary>
        public void Place(Camera cam)
        {
            if (root == null || cam == null || !root.activeSelf) return;
            if (root.transform.parent != cam.transform) root.transform.SetParent(cam.transform, false);
            float distance = cam.nearClipPlane * 2.5f;
            float unitsPerPixel = 2f * distance * Mathf.Tan(cam.fieldOfView * 0.5f * Mathf.Deg2Rad) / Mathf.Max(1, cam.pixelHeight);
            float left = cam.pixelWidth * 0.5f - (Margin + Width) * scale, top = cam.pixelHeight * 0.5f - Top * scale;
            root.transform.localRotation = Quaternion.identity;
            root.transform.localScale = Vector3.one * unitsPerPixel;
            root.transform.localPosition = new Vector3(left * unitsPerPixel, top * unitsPerPixel, distance);
        }

        public void Destroy()
        {
            if (root != null) Object.DestroyImmediate(root);
            if (panelMaterial != null) Object.DestroyImmediate(panelMaterial);
            root = null;
            texts.Clear();
        }

        private void Build(Camera cam)
        {
            if (root != null) return;
            font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            root = new GameObject("Name card") { hideFlags = HideFlags.DontSave };
            root.transform.SetParent(cam.transform, false);
            var quad = GameObject.CreatePrimitive(PrimitiveType.Quad);
            quad.name = "Panel";
            quad.hideFlags = HideFlags.DontSave;
            Object.DestroyImmediate(quad.GetComponent<Collider>());
            quad.transform.SetParent(root.transform, false);
            panel = quad.GetComponent<MeshRenderer>();
            // Unity's own plain-colour shader: always in a build, blended, and before everything (the card is nearer
            // the lens than anything of the room can come).
            panelMaterial = new Material(Shader.Find("Hidden/Internal-Colored")) { hideFlags = HideFlags.DontSave };
            panelMaterial.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
            panelMaterial.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
            panelMaterial.SetInt("_Cull", (int)UnityEngine.Rendering.CullMode.Off);
            panelMaterial.SetInt("_ZWrite", 0);
            panelMaterial.SetInt("_ZTest", (int)UnityEngine.Rendering.CompareFunction.Always);
            panelMaterial.SetColor("_Color", Panel);
            panelMaterial.renderQueue = 4000;
            panel.sharedMaterial = panelMaterial;
            panel.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            panel.receiveShadows = false;
            if (font != null) font.material.renderQueue = 4001;       // the text after its panel
        }

        private TextMesh NewText()
        {
            var go = new GameObject("Line") { hideFlags = HideFlags.DontSave };
            go.transform.SetParent(root.transform, false);
            var t = go.AddComponent<TextMesh>();
            t.font = font;
            t.anchor = TextAnchor.UpperLeft;
            t.alignment = TextAlignment.Left;
            t.richText = false;
            var r = go.GetComponent<MeshRenderer>();
            if (font != null) r.sharedMaterial = font.material;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            r.receiveShadows = false;
            texts.Add(t);
            return t;
        }
    }
}
