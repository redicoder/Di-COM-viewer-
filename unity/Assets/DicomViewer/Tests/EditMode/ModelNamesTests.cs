using System.Collections.Generic;
using System.IO;
using DicomViewer.AnatomyLab;
using NUnit.Framework;
using UnityEngine;

namespace DicomViewer.Tests
{
    /// <summary>
    /// A touched structure is found and named: the names table and a teacher's corrections, what the card says
    /// (a drawn structure is told apart), and which mesh is in front under a pixel.
    /// </summary>
    public class ModelNamesTests
    {
        private const string Table = @"{
            ""layers"": [{""key"": ""skeleton"", ""la"": ""Skeleton"", ""en"": ""Skeleton"", ""it"": ""Scheletro""}, {""key"": ""organs"", ""la"": ""Viscera"", ""en"": ""Organs"", ""it"": ""Organi""}],
            ""sources"": [{""key"": ""ct"", ""la"": ""Forma rilevata dalla TC."", ""en"": ""Shape read from the CT."", ""it"": ""Forma rilevata dalla TC.""},
                          {""key"": ""drawn"", ""la"": ""Disegnato."", ""en"": ""Drawn."", ""it"": ""Disegnato.""}],
            ""notes"": [{""key"": ""tooth"", ""la"": ""Una stima."", ""en"": ""An estimate."", ""it"": ""Una stima.""}],
            ""structures"": [
                {""key"": ""left femur"", ""layer"": ""skeleton"", ""la"": ""Femur sinistrum"", ""en"": ""Left femur"", ""it"": ""Femore sinistro"", ""from"": ""ct"", ""drawn"": false, ""note"": """"},
                {""key"": ""left facial nerve"", ""layer"": ""organs"", ""la"": ""Nervus facialis sinister"", ""en"": ""Left facial nerve"", ""it"": ""Nervo facciale sinistro"", ""from"": ""drawn"", ""drawn"": true, ""note"": """"},
                {""key"": ""upper left canine"", ""layer"": ""skeleton"", ""la"": ""Dens caninus superior sinister"", ""en"": ""Upper left canine"", ""it"": """", ""from"": ""ct"", ""drawn"": false, ""note"": ""tooth""}]}";

        [Test]
        public void AStructureIsNamedInThreeLanguagesByItsMeshsName()
        {
            ModelNames names = ModelNames.Parse(Table);
            Assert.That(names.Count, Is.EqualTo(3));
            NameEntry femur = names.Find("left femur");
            Assert.That(names.Name(femur, NameLanguage.Italian), Is.EqualTo("Femore sinistro"));
            Assert.That(names.Name(femur, NameLanguage.English), Is.EqualTo("Left femur"));
            Assert.That(names.Name(femur, NameLanguage.Latin), Is.EqualTo("Femur sinistrum"));
            Assert.That(names.Layer("skeleton", NameLanguage.Italian), Is.EqualTo("Scheletro"));
            Assert.That(names.Source(femur, NameLanguage.English), Is.EqualTo("Shape read from the CT."));
            Assert.That(names.Source(femur, NameLanguage.Latin), Is.EqualTo("Forma rilevata dalla TC."), "with Latin names the card speaks Italian");
            Assert.That(names.Find("right femur"), Is.Null);
            Assert.That(names.Find(null), Is.Null);
            NameEntry canine = names.Find("upper left canine");
            Assert.That(names.Name(canine, NameLanguage.Italian), Is.EqualTo("Upper left canine"), "a language the table has no name in: the English");
            Assert.That(names.Note(canine, NameLanguage.English), Is.EqualTo("An estimate."));
            Assert.That(ModelNames.Parse(null).Count, Is.EqualTo(0), "no file: an empty table, and every structure is shown by its mesh's name");
        }

        [Test]
        public void ATeachersCorrectionsAreReadAfterTheTableAndChangeOnlyWhatTheyName()
        {
            const string fixes = @"{""structures"": [{""key"": ""left femur"", ""it"": ""Femore di sinistra""}, {""key"": ""no such structure"", ""it"": ""x""}]}";
            ModelNames names = ModelNames.Parse(Table, fixes);
            NameEntry femur = names.Find("left femur");
            Assert.That(femur.it, Is.EqualTo("Femore di sinistra"));
            Assert.That(femur.la, Is.EqualTo("Femur sinistrum"), "what the correction leaves out stays");
            Assert.That(femur.layer, Is.EqualTo("skeleton"));
            Assert.That(names.Corrected, Is.EqualTo(1));
            Assert.That(names.Count, Is.EqualTo(3), "a correction adds no structure");
        }

        [Test]
        public void TheCardNamesTheStructureLargeTheOtherLanguagesUnderItAndSaysWhatIsDrawn()
        {
            ModelNames names = ModelNames.Parse(Table);
            List<ModelCard.Line> femur = ModelCard.Compose(names, names.Find("left femur"), "left femur", NameLanguage.Italian);
            Assert.That(femur[0].text, Is.EqualTo("Femore sinistro"));
            Assert.That(femur[0].size, Is.GreaterThan(femur[1].size));
            Assert.That(femur[1].text, Does.StartWith("LA").And.EndWith("Femur sinistrum"));
            Assert.That(femur[2].text, Does.StartWith("EN").And.EndWith("Left femur"));
            Assert.That(femur[3].text, Is.EqualTo("Strato: Scheletro"));
            Assert.That(femur[4].text, Is.EqualTo("Forma rilevata dalla TC."));
            Assert.That(femur[4].colour, Is.EqualTo(ModelCard.Faint));
            List<ModelCard.Line> nerve = ModelCard.Compose(names, names.Find("left facial nerve"), "left facial nerve", NameLanguage.English);
            Assert.That(nerve[0].text, Is.EqualTo("Left facial nerve"));
            Assert.That(nerve[3].text, Is.EqualTo("Layer: Organs"));
            Assert.That(ModelCard.Compose(names, names.Find("left femur"), "left femur", NameLanguage.Latin)[3].text, Is.EqualTo("Strato: Scheletro"),
                        "with Latin names the card's own words, and the layer's name with them, are Italian");
            Assert.That(nerve[4].text, Is.EqualTo("Drawn."));
            Assert.That(nerve[4].colour, Is.EqualTo(ModelCard.Amber), "what is drawn and not read from the body is told apart");
            List<ModelCard.Line> unknown = ModelCard.Compose(names, null, "some mesh", NameLanguage.Italian);
            Assert.That(unknown.Count, Is.EqualTo(1));
            Assert.That(unknown[0].text, Is.EqualTo("some mesh"), "a structure the table does not have is shown by its mesh's name");
        }

        [Test]
        public void ALongNameIsBrokenAtItsWords()
        {
            List<string> lines = ModelCard.Wrap(null, "Cartilagine articolare del condilo laterale della tibia sinistra", 20, 260f);   // (no font: ten pixels a letter)
            Assert.That(lines.Count, Is.GreaterThan(1));
            foreach (string line in lines) Assert.That(line.Length * 10f, Is.LessThanOrEqualTo(260f));
            Assert.That(string.Join(" ", lines), Is.EqualTo("Cartilagine articolare del condilo laterale della tibia sinistra"));
            Assert.That(ModelCard.Wrap(null, "Femur", 20, 260f), Is.EqualTo(new List<string> { "Femur" }));
        }

        [Test]
        public void TheTableTheAppShipsNamesTheBodysStructures()
        {
            string path = Path.Combine(Application.streamingAssetsPath, ModelNames.Folder, ModelNames.File);
            if (!File.Exists(path)) Assert.Ignore("no names table yet (the model's build writes it)");
            ModelNames names = ModelNames.Parse(File.ReadAllText(path));
            Assert.That(names.Count, Is.GreaterThan(400));
            NameEntry femur = names.Find("left femur");
            Assert.That(femur, Is.Not.Null);
            Assert.That(names.Name(femur, NameLanguage.Italian), Is.EqualTo("Femore sinistro"));
            Assert.That(names.Name(femur, NameLanguage.Latin), Is.EqualTo("Femur sinistrum"));
            Assert.That(names.Layer(femur.layer, NameLanguage.Italian), Is.EqualTo("Scheletro"));
            Assert.That(names.Source(femur, NameLanguage.Italian), Is.Not.Empty);
            Assert.That(names.Find("left facial nerve").drawn, Is.True);
            Assert.That(names.Find("liver").drawn, Is.False);
        }

        // ---- which mesh is under a pixel ----------------------------------------------------------------------

        private static (Camera cam, Renderer near, Renderer far, RenderTexture rt) Stage()
        {
            Shader shader = Shader.Find("DicomViewer/LabModel");
            Assert.That(shader, Is.Not.Null);
            var cam = new GameObject("pick camera").AddComponent<Camera>();
            cam.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
            cam.fieldOfView = 60f;
            cam.nearClipPlane = 0.1f;
            var rt = new RenderTexture(200, 100, 24);
            cam.targetTexture = rt;
            Renderer Cube(string name, Vector3 at, float size)
            {
                var r = GameObject.CreatePrimitive(PrimitiveType.Cube).GetComponent<Renderer>();
                r.name = name;
                r.transform.position = at;
                r.transform.localScale = Vector3.one * size;
                r.sharedMaterial = new Material(shader);
                return r;
            }
            return (cam, Cube("near", new Vector3(0f, 0f, 2f), 0.5f), Cube("far", new Vector3(0f, 0f, 4f), 2f), rt);
        }

        private static void Clear(Camera cam, RenderTexture rt, params Renderer[] renderers)
        {
            cam.targetTexture = null;
            Object.DestroyImmediate(rt);
            Object.DestroyImmediate(cam.gameObject);
            foreach (Renderer r in renderers)
            {
                Object.DestroyImmediate(r.sharedMaterial);
                Object.DestroyImmediate(r.gameObject);
            }
        }

        [Test]
        public void TheMeshInFrontUnderAPixelIsTheOnePicked()
        {
            if (SystemInfo.graphicsDeviceType == UnityEngine.Rendering.GraphicsDeviceType.Null) Assert.Ignore("needs a graphics device");
            var (cam, near, far, rt) = Stage();
            var both = new List<Renderer> { far, near };
            var middle = new Vector2(100f, 50f);
            Assert.That(ModelPick.At(cam, middle, both), Is.SameAs(near), "the small cube stands before the large one");
            Assert.That(ModelPick.At(cam, new Vector2(100f + 24f, 50f), both), Is.SameAs(far), "beside the small cube the large one behind it shows");
            Assert.That(ModelPick.At(cam, new Vector2(3f, 3f), both), Is.Null, "in the picture's corner there is neither");
            near.gameObject.SetActive(false);
            Assert.That(ModelPick.At(cam, middle, both), Is.SameAs(far), "a mesh that is off cannot be touched");
            near.gameObject.SetActive(true);
            Assert.That(ModelPick.At(cam, middle, new List<Renderer> { far }), Is.SameAs(far), "nor one that is not offered");
            Assert.That(ModelPick.At(cam, new Vector2(-5f, 50f), both), Is.Null, "a pixel outside the picture");
            Clear(cam, rt, near, far);
        }

        [Test]
        public void TheWholePictureIsReadInNumbersTheRightWayUp()
        {
            if (SystemInfo.graphicsDeviceType == UnityEngine.Rendering.GraphicsDeviceType.Null) Assert.Ignore("needs a graphics device");
            var (cam, near, far, rt) = Stage();
            near.transform.position = new Vector3(0f, 0.5f, 2f);          // the small cube lifted: in the picture's upper half
            var both = new List<Renderer> { far, near };
            int[] map = ModelPick.Map(cam, both, out int w, out int h);
            Assert.That(w, Is.EqualTo(200));
            Assert.That(h, Is.EqualTo(100));
            Assert.That(map.Length, Is.EqualTo(200 * 100));
            Assert.That(map[72 * 200 + 100], Is.EqualTo(2), "above the middle (rows count from the bottom): the small cube, the second offered");
            Assert.That(map[28 * 200 + 100], Is.EqualTo(1), "below the middle: the large cube behind");
            Assert.That(map[3 * 200 + 3], Is.EqualTo(0), "in the corner: nothing");
            // What a tap picks is what the map has at that pixel.
            Assert.That(ModelPick.At(cam, new Vector2(100f, 72f), both), Is.SameAs(near));
            Assert.That(ModelPick.At(cam, new Vector2(100f, 28f), both), Is.SameAs(far));
            Clear(cam, rt, near, far);
        }

        [Test]
        public void ATapPicksTintsAndNamesAndASecondTapPutsTheCardAway()
        {
            if (SystemInfo.graphicsDeviceType == UnityEngine.Rendering.GraphicsDeviceType.Null) Assert.Ignore("needs a graphics device");
            var (cam, near, far, rt) = Stage();
            var body = new GameObject("body").AddComponent<ModelBody>();
            var layer = new GameObject("skeleton");
            near.transform.SetParent(layer.transform, true);
            far.transform.SetParent(layer.transform, true);
            var hair = GameObject.CreatePrimitive(PrimitiveType.Cube).GetComponent<Renderer>();     // strands before everything: not to be touched
            hair.name = "hair chest";
            hair.transform.position = new Vector3(0f, 0f, 1f);
            hair.transform.localScale = Vector3.one * 0.3f;
            hair.sharedMaterial = new Material(Shader.Find("DicomViewer/LabModel"));
            hair.transform.SetParent(layer.transform, true);
            body.nested = true;
            body.Add("skeleton", layer);
            Assert.That(body.Touchable(), Has.No.Member(hair));
            Assert.That(body.Touchable().Count, Is.EqualTo(2));

            var middle = new Vector2(100f, 50f);
            Assert.That(body.TapAt(cam, middle), Is.SameAs(near));
            Assert.That(body.Card.Shown, Is.True);
            Assert.That(body.Card.Lines[0].text, Is.EqualTo("near"), "a mesh the names table does not have is shown by its own name");
            Assert.That(near.sharedMaterial.GetFloat("_Picked"), Is.EqualTo(1f), "the picked structure is marked");
            Assert.That(far.sharedMaterial.GetFloat("_Picked"), Is.EqualTo(0f));
            Assert.That(body.TapAt(cam, new Vector2(124f, 50f)), Is.SameAs(far), "a tap on another structure picks that one");
            Assert.That(near.sharedMaterial.GetFloat("_Picked"), Is.EqualTo(0f), "and the first is marked no longer");
            Assert.That(far.sharedMaterial.GetFloat("_Picked"), Is.EqualTo(1f));
            Assert.That(body.TapAt(cam, new Vector2(124f, 50f)), Is.Null, "a second tap on the picked structure puts the card away");
            Assert.That(body.Card.Shown, Is.False);
            Assert.That(far.sharedMaterial.GetFloat("_Picked"), Is.EqualTo(0f));
            body.TapAt(cam, middle);
            Assert.That(body.TapAt(cam, new Vector2(3f, 3f)), Is.Null, "so does a tap beside the body");
            body.TapAt(cam, middle);
            body.Show("skeleton", false);
            Assert.That(body.Picked, Is.Null, "and taking its layer away");
            Assert.That(near.sharedMaterial.GetFloat("_Picked"), Is.EqualTo(0f));

            Object.DestroyImmediate(hair.sharedMaterial);
            hair.transform.SetParent(null, true);                        // (the body would take its layer's meshes with it)
            near.transform.SetParent(null, true);
            far.transform.SetParent(null, true);
            Object.DestroyImmediate(hair.gameObject);
            Object.DestroyImmediate(body.gameObject);
            Clear(cam, rt, near, far);
        }

        // ---- taking a structure off ---------------------------------------------------------------------------

        [Test]
        public void AStructureIsTakenOffAndPutBackAndWhatLayBehindItIsTouched()
        {
            if (SystemInfo.graphicsDeviceType == UnityEngine.Rendering.GraphicsDeviceType.Null) Assert.Ignore("needs a graphics device");
            var (cam, near, far, rt) = Stage();
            var body = new GameObject("body").AddComponent<ModelBody>();
            var bones = new GameObject("skeleton");
            near.transform.SetParent(bones.transform, true);
            far.transform.SetParent(bones.transform, true);
            var skinLayer = new GameObject("skin");
            var skin = GameObject.CreatePrimitive(PrimitiveType.Cube).GetComponent<Renderer>();      // behind both: in nobody's way
            skin.name = "skin";
            skin.transform.position = new Vector3(0f, 0f, 9f);
            skin.transform.localScale = Vector3.one * 3f;
            skin.sharedMaterial = new Material(Shader.Find("DicomViewer/LabModel"));
            skin.transform.SetParent(skinLayer.transform, true);
            body.nested = true;
            body.Add("skin", skinLayer);
            body.Add("skeleton", bones);
            var middle = new Vector2(100f, 50f);

            Assert.That(body.LayerOf(near).name, Is.EqualTo("skeleton"));
            Assert.That(body.CanHide(near), Is.True);
            Assert.That(body.CanHide(skin), Is.False, "the skin goes off with its own button, all of it together");
            Assert.That(body.Hide(skin), Is.False);
            Assert.That(body.Hide(null), Is.False);

            Assert.That(body.TapAt(cam, middle), Is.SameAs(near));
            Assert.That(body.Hide(near), Is.True);
            Assert.That(near.enabled, Is.False, "what is taken off is no longer drawn");
            Assert.That(body.Picked, Is.Null, "its card goes with it");
            Assert.That(body.Card.Shown, Is.False);
            Assert.That(near.sharedMaterial.GetFloat("_Picked"), Is.EqualTo(0f));
            Assert.That(body.Touchable(), Has.No.Member(near));
            Assert.That(body.TapAt(cam, middle), Is.SameAs(far), "what lay behind it is touched now");
            Assert.That(body.Hide(far), Is.True);
            Assert.That(body.Hidden.Count, Is.EqualTo(2));
            Assert.That(body.Hide(far), Is.False, "what is off cannot be taken off again");

            Assert.That(body.ShowLast(), Is.SameAs(far), "the last one taken off comes back first");
            Assert.That(far.enabled, Is.True);
            Assert.That(near.enabled, Is.False);
            body.LookAt("skeleton");
            body.LookAt("skin");
            Assert.That(near.enabled, Is.False, "looking at another layer and back does not put it back");
            body.ShowAll();
            Assert.That(near.enabled, Is.True);
            Assert.That(body.Hidden.Count, Is.EqualTo(0));
            Assert.That(body.ShowLast(), Is.Null, "nothing is off any more");
            Assert.That(body.TapAt(cam, middle), Is.SameAs(near), "and it is in front again");
            body.Select(null, cam);

            // What lay inside a structure that is taken off loses most of the shadow baked into it (it was baked as
            // buried); what lay clear of it keeps its own; and put back, all is as it was.
            near.transform.position = new Vector3(0f, 0f, 4f);            // the small cube inside the large one now
            float baked = near.sharedMaterial.GetFloat("_Occlusion");
            Assert.That(baked, Is.GreaterThan(0.1f));
            Assert.That(body.Hide(far), Is.True);
            Assert.That(near.sharedMaterial.GetFloat("_Occlusion"), Is.EqualTo(baked * ModelBody.Uncovered).Within(1e-5f));
            Assert.That(skin.sharedMaterial.GetFloat("_Occlusion"), Is.EqualTo(baked).Within(1e-5f), "the skin's layer is not touched");
            body.ShowAll();
            Assert.That(near.sharedMaterial.GetFloat("_Occlusion"), Is.EqualTo(baked).Within(1e-5f));
            near.transform.position = new Vector3(0f, 0f, 2f);            // clear of the large one again
            Assert.That(body.Hide(far), Is.True);
            Assert.That(near.sharedMaterial.GetFloat("_Occlusion"), Is.EqualTo(baked).Within(1e-5f), "what did not lie in its room keeps its shadow");
            Assert.That(body.ShowLast(), Is.SameAs(far));

            Object.DestroyImmediate(skin.sharedMaterial);
            skin.transform.SetParent(null, true);                       // (the body would take its layers' meshes with it)
            near.transform.SetParent(null, true);
            far.transform.SetParent(null, true);
            Object.DestroyImmediate(skin.gameObject);
            Object.DestroyImmediate(body.gameObject);
            Clear(cam, rt, near, far);
        }
    }
}
