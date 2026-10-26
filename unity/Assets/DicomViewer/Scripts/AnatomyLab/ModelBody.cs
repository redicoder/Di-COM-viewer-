using System;
using System.Collections.Generic;
using UnityEngine;

namespace DicomViewer.AnatomyLab
{
    /// <summary>
    /// The modelled body as layers on the table, outermost first: the skin (body.glb), the muscles (muscles.glb),
    /// the skeleton (skeleton.glb), later the organs. Each layer is a model laid by ModelLab.Lay at the same height
    /// and place. The models are generated one by one and do not nest exactly (the muscle man is broader than the
    /// skin), so only the outermost layer that is on is drawn: take the skin away and the muscles show, take the
    /// muscles away and the skeleton shows. Buttons at the top of the screen (big enough for a finger) pick the
    /// layer to see while the scene plays.
    /// </summary>
    public class ModelBody : MonoBehaviour
    {
        [Serializable]
        public class Layer
        {
            public string name;
            public GameObject model;
            public bool shown = true;
        }

        public List<Layer> layers = new List<Layer>();

        public static readonly string[] LayerNames = { "body", "muscles", "skeleton" };
        public static readonly string[] LayerLabels = { "Skin", "Muscles", "Skeleton" };

        public void Add(string name, GameObject model)
        {
            layers.Add(new Layer { name = name, model = model, shown = true });
            model.transform.SetParent(transform, true);
            Apply();
        }

        public Layer Find(string name) => layers.Find(l => l.name == name);

        public bool Shown(string name) => Find(name)?.shown ?? false;

        /// <summary>The layer that is drawn: the outermost one that is on; null when every layer is off.</summary>
        public Layer Visible => layers.Find(l => l.shown && l.model != null);

        public void Show(string name, bool on)
        {
            Layer l = Find(name);
            if (l == null) return;
            l.shown = on;
            Apply();
        }

        /// <summary>Looks at this layer: the layers outside it go off, it and the ones inside come on.</summary>
        public void LookAt(string name)
        {
            bool outside = true;
            foreach (Layer l in layers)
            {
                if (l.name == name) outside = false;
                l.shown = !outside;
            }
            Apply();
        }

        private void Apply()
        {
            Layer visible = Visible;
            foreach (Layer l in layers)
                if (l.model != null) l.model.SetActive(l == visible);
        }

        private void OnGUI()
        {
            float s = Mathf.Max(1f, Screen.dpi > 0f ? Screen.dpi / 96f : 1f);
            float h = 44f * s, w = 150f * s, x = 12f * s, y = 12f * s;
            GUI.skin.button.fontSize = Mathf.RoundToInt(18f * s);
            Layer visible = Visible;
            foreach (Layer l in layers)
            {
                int k = Array.IndexOf(LayerNames, l.name);
                string label = (l == visible ? "● " : "") + (k >= 0 ? LayerLabels[k] : l.name);
                if (GUI.Button(new Rect(x, y, w, h), label)) LookAt(l.name);
                x += w + 8f * s;
            }
        }
    }
}
