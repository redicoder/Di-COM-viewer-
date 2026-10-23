using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace DicomViewer.AnatomyLab
{
    /// <summary>
    /// A structure taken out of the body as a piece: its voxels (one object index of BodyLabels) made into a mesh
    /// (FieldMesh: the label's indicator blurred and contoured), with its own photographed surface (each vertex
    /// keeps where it came from in the volume, LabOrganPiece.shader reads the colour there), under the body's
    /// transform in the body's metres. It comes away in the hand (Hold / Follow), is let go (Drop) onto a spot on
    /// the tray or table where it settles lying flat, and goes back when the structure is put back (destroyed).
    /// Large objects (a whole musculature) are meshed on a coarser grid so the piece is ready in well under a
    /// second.
    /// </summary>
    public class OrganPiece : MonoBehaviour
    {
        public const int MaxCells = 2_500_000;

        public PhotoBody Body { get; private set; }
        public int Index { get; private set; }
        public string Name { get; private set; }
        public Bounds LocalBounds { get; private set; }            // of the mesh, body metres

        private Mesh mesh;
        private Material material;
        private enum State { Placed, Held, Dropping, Resting }
        private State state = State.Placed;
        private Vector3 holdTarget;
        private Vector3 dropFrom, dropTo, dropDown;
        private Quaternion dropFromRot, dropToRot;
        private float dropT;
        private const float DropSeconds = 0.55f;

        /// <summary>Builds the piece for one object of the body's labels; null when the object has no voxels.</summary>
        public static OrganPiece Create(PhotoBody body, int index)
        {
            if (body == null || body.Labels == null || index <= 0) return null;
            BodyLabels labels = body.Labels;
            Vector3Int d = labels.Dims;
            byte[] lab = labels.Index;
            // The object's box, in voxels.
            int x0 = d.x, y0 = d.y, z0 = d.z, x1 = -1, y1 = -1, z1 = -1;
            for (int z = 0; z < d.z; z++)
            for (int y = 0; y < d.y; y++)
            {
                int row = (z * d.y + y) * d.x;
                for (int x = 0; x < d.x; x++)
                    if (lab[row + x] == index)
                    {
                        if (x < x0) x0 = x; if (x > x1) x1 = x;
                        if (y < y0) y0 = y; if (y > y1) y1 = y;
                        if (z < z0) z0 = z; if (z > z1) z1 = z;
                    }
            }
            if (x1 < 0) return null;
            // A grid two cells beyond the box, at the voxels' step or coarser for a very large object.
            int step = 1;
            long cells = (long)(x1 - x0 + 5) * (y1 - y0 + 5) * (z1 - z0 + 5);
            while (cells / ((long)step * step * step) > MaxCells) step++;
            Vector3Int lo = new Vector3Int(x0 - 2 * step, y0 - 2 * step, z0 - 2 * step);
            Vector3Int n = new Vector3Int((x1 - x0) / step + 5, (y1 - y0) / step + 5, (z1 - z0) / step + 5);
            var f = new float[n.x * n.y * n.z];
            for (int z = 0; z < n.z; z++)
            for (int y = 0; y < n.y; y++)
            for (int x = 0; x < n.x; x++)
            {
                int vx = lo.x + x * step, vy = lo.y + y * step, vz = lo.z + z * step;
                bool inside = vx >= 0 && vy >= 0 && vz >= 0 && vx < d.x && vy < d.y && vz < d.z && lab[(vz * d.y + vy) * d.x + vx] == index;
                f[(z * n.y + y) * n.x + x] = inside ? -1f : 1f;
            }
            f = FieldMesh.Blur(f, n);
            var verts = new List<Vector3>();
            var tris = new List<int>();
            FieldMesh.SurfaceNets(f, n, verts, tris);
            if (tris.Count == 0) return null;

            // Grid units -> voxel coordinates -> body metres, keeping the volume coordinate per vertex for the colour.
            Vector3 spacing = body.Space.SpacingMm, sizeMm = body.Space.SizeMm, sizeM = body.SizeM;
            var positions = new Vector3[verts.Count];
            var uvw = new Vector3[verts.Count];
            for (int i = 0; i < verts.Count; i++)
            {
                Vector3 v = verts[i];
                Vector3 mm = new Vector3((lo.x + v.x * step + 0.5f) * spacing.x, (lo.y + v.y * step + 0.5f) * spacing.y, (lo.z + v.z * step + 0.5f) * spacing.z);
                Vector3 u = new Vector3(mm.x / sizeMm.x, mm.y / sizeMm.y, mm.z / sizeMm.z);
                uvw[i] = u;
                positions[i] = new Vector3((u.x - 0.5f) * sizeM.x, (u.y - 0.5f) * sizeM.y, (u.z - 0.5f) * sizeM.z);
            }
            var m = new Mesh { name = "Piece", hideFlags = HideFlags.DontSave, indexFormat = IndexFormat.UInt32 };
            m.SetVertices(positions);
            m.SetUVs(0, uvw);
            m.SetTriangles(tris, 0);
            m.RecalculateNormals();
            m.RecalculateBounds();

            Shader shader = Shader.Find("DicomViewer/LabOrganPiece");
            if (shader == null) { Debug.LogWarning("Shader DicomViewer/LabOrganPiece not found"); Object.Destroy(m); return null; }
            var go = new GameObject("Piece " + labels.Name(index)) { hideFlags = HideFlags.DontSave };
            go.transform.SetParent(body.transform, false);
            var piece = go.AddComponent<OrganPiece>();
            piece.Body = body;
            piece.Index = index;
            piece.Name = labels.Name(index);
            piece.mesh = m;
            piece.LocalBounds = m.bounds;
            piece.material = new Material(shader) { name = "Piece" };
            piece.material.SetTexture("_ColorTex", body.ColourTexture);
            piece.material.SetVector("_SizeMm", sizeMm);
            go.AddComponent<MeshFilter>().sharedMesh = m;
            var r = go.AddComponent<MeshRenderer>();
            r.sharedMaterial = piece.material;
            r.shadowCastingMode = ShadowCastingMode.On;
            _ = r.bounds;                                              // outside Play mode the culling bounds are not refreshed on their own
            return piece;
        }

        /// <summary>The piece's centre, world.</summary>
        public Vector3 Centre => transform.TransformPoint(LocalBounds.center);

        /// <summary>Taken in hand: from now on it follows the hand's target (Follow) until Drop.</summary>
        public void Hold()
        {
            state = State.Held;
            holdTarget = Centre;
        }

        public bool IsHeld => state == State.Held;

        /// <summary>Where the hand wants the piece's centre, world; the piece eases after it.</summary>
        public void Follow(Vector3 centreWorld) => holdTarget = centreWorld;

        /// <summary>Let go: glides to a spot (world) and settles there lying flat, its lowest point on the surface whose
        /// normal is -down (world). seconds = 0 puts it there at once.</summary>
        public void Drop(Vector3 spotWorld, Vector3 downWorld, float seconds = DropSeconds)
        {
            downWorld = downWorld.normalized;
            dropDown = downWorld;
            dropFrom = transform.position;
            dropFromRot = transform.rotation;
            // Lying flat: the piece's thinnest local axis turns to point down.
            Vector3 ext = LocalBounds.extents;
            Vector3 thin = ext.x <= ext.y && ext.x <= ext.z ? Vector3.right : ext.y <= ext.z ? Vector3.up : Vector3.forward;
            Vector3 thinWorld = transform.TransformDirection(thin);
            if (Vector3.Dot(thinWorld, downWorld) < 0f) thinWorld = -thinWorld;
            dropToRot = Quaternion.FromToRotation(thinWorld, downWorld) * transform.rotation;
            // The position that puts the box's lowest point on the surface at the spot.
            float lowest = float.NegativeInfinity;
            Vector3 c = LocalBounds.center;
            for (int i = 0; i < 8; i++)
            {
                Vector3 corner = c + Vector3.Scale(ext, new Vector3((i & 1) * 2 - 1, ((i >> 1) & 1) * 2 - 1, ((i >> 2) & 1) * 2 - 1));
                Vector3 w = dropToRot * (transform.lossyScale.x * corner);           // uniform scale assumed
                lowest = Mathf.Max(lowest, Vector3.Dot(w, downWorld));
            }
            dropTo = spotWorld - downWorld * lowest;
            dropT = 0f;
            state = seconds <= 0f ? State.Resting : State.Dropping;
            if (seconds <= 0f) transform.SetPositionAndRotation(dropTo, dropToRot);
            _ = GetComponent<Renderer>().bounds;
        }

        private void Update()
        {
            float dt = Time.deltaTime;
            switch (state)
            {
                case State.Held:
                {
                    Vector3 offset = transform.position - Centre;
                    Vector3 want = holdTarget + offset;
                    transform.position = Vector3.Lerp(transform.position, want, 1f - Mathf.Exp(-dt * 14f));
                    break;
                }
                case State.Dropping:
                {
                    dropT = Mathf.Min(1f, dropT + dt / DropSeconds);
                    float s = dropT * dropT * (3f - 2f * dropT);
                    Vector3 p = Vector3.Lerp(dropFrom, dropTo, s) - dropDown * (0.06f * Mathf.Sin(s * Mathf.PI));   // a small arc
                    transform.SetPositionAndRotation(p, Quaternion.Slerp(dropFromRot, dropToRot, s));
                    if (dropT >= 1f) state = State.Resting;
                    break;
                }
            }
        }

        private void OnDestroy()
        {
            if (mesh != null) Kill(mesh);
            if (material != null) Kill(material);
        }

        private static void Kill(Object o)
        {
            if (Application.isPlaying) Destroy(o);
            else DestroyImmediate(o);
        }
    }
}
