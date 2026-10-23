using System.Collections.Generic;
using UnityEngine;

namespace DicomViewer.AnatomyLab
{
    /// <summary>
    /// A mesh from a scalar field on a grid, by naive surface nets (as HandMesh does for the glove): one vertex per
    /// cell the zero level crosses, at the mean of its edge crossings; a quad across every grid edge whose ends differ
    /// in sign. Smooth, watertight, no lookup tables. The field is negative inside. Vertices come back in grid units
    /// (cell = 1) from the grid's origin; the caller scales them.
    /// </summary>
    public static class FieldMesh
    {
        public static void SurfaceNets(float[] f, Vector3Int n, List<Vector3> vertices, List<int> triangles)
        {
            int nx = n.x, ny = n.y, nz = n.z;
            int I(int x, int y, int z) => (z * ny + y) * nx + x;
            var cellVertex = new int[(nx - 1) * (ny - 1) * (nz - 1)];
            int C(int x, int y, int z) => (z * (ny - 1) + y) * (nx - 1) + x;
            int[,] edges =
            {
                { 0, 1 }, { 2, 3 }, { 4, 5 }, { 6, 7 }, { 0, 2 }, { 1, 3 }, { 4, 6 }, { 5, 7 }, { 0, 4 }, { 1, 5 }, { 2, 6 }, { 3, 7 },
            };
            var corner = new Vector3Int[8];
            for (int i = 0; i < 8; i++) corner[i] = new Vector3Int(i & 1, (i >> 1) & 1, (i >> 2) & 1);
            for (int z = 0; z < nz - 1; z++)
            for (int y = 0; y < ny - 1; y++)
            for (int x = 0; x < nx - 1; x++)
            {
                Vector3 sum = Vector3.zero;
                int count = 0;
                for (int e = 0; e < 12; e++)
                {
                    Vector3Int a = corner[edges[e, 0]], b = corner[edges[e, 1]];
                    float fa = f[I(x + a.x, y + a.y, z + a.z)], fb = f[I(x + b.x, y + b.y, z + b.z)];
                    if ((fa < 0f) == (fb < 0f)) continue;
                    float t = fa / (fa - fb);
                    sum += (Vector3)a + ((Vector3)(b - a)) * t;
                    count++;
                }
                if (count == 0) { cellVertex[C(x, y, z)] = -1; continue; }
                cellVertex[C(x, y, z)] = vertices.Count;
                vertices.Add(new Vector3(x, y, z) + sum / count);
            }

            void Quad(int c0, int c1, int c2, int c3, bool flip)
            {
                if (c0 < 0 || c1 < 0 || c2 < 0 || c3 < 0) return;
                if (flip) { triangles.Add(c0); triangles.Add(c2); triangles.Add(c1); triangles.Add(c0); triangles.Add(c3); triangles.Add(c2); }
                else { triangles.Add(c0); triangles.Add(c1); triangles.Add(c2); triangles.Add(c0); triangles.Add(c2); triangles.Add(c3); }
            }
            for (int z = 1; z < nz - 1; z++)
            for (int y = 1; y < ny - 1; y++)
            for (int x = 1; x < nx - 1; x++)
            {
                float f0 = f[I(x, y, z)];
                bool inside = f0 < 0f;
                if (x + 1 < nx && (f[I(x + 1, y, z)] < 0f) != inside)
                    Quad(cellVertex[C(x, y - 1, z - 1)], cellVertex[C(x, y, z - 1)], cellVertex[C(x, y, z)], cellVertex[C(x, y - 1, z)], inside);
                if (y + 1 < ny && (f[I(x, y + 1, z)] < 0f) != inside)
                    Quad(cellVertex[C(x - 1, y, z - 1)], cellVertex[C(x - 1, y, z)], cellVertex[C(x, y, z)], cellVertex[C(x, y, z - 1)], inside);
                if (z + 1 < nz && (f[I(x, y, z + 1)] < 0f) != inside)
                    Quad(cellVertex[C(x - 1, y - 1, z)], cellVertex[C(x, y - 1, z)], cellVertex[C(x, y, z)], cellVertex[C(x - 1, y, z)], inside);
            }
        }

        /// <summary>A 3 x 3 x 3 box blur of a field (in place through a copy): the voxel steps of a label become a surface.</summary>
        public static float[] Blur(float[] f, Vector3Int n)
        {
            var g = new float[f.Length];
            int nx = n.x, ny = n.y, nz = n.z;
            for (int z = 0; z < nz; z++)
            for (int y = 0; y < ny; y++)
            for (int x = 0; x < nx; x++)
            {
                float sum = 0f;
                int count = 0;
                for (int dz = -1; dz <= 1; dz++)
                {
                    int zz = z + dz; if (zz < 0 || zz >= nz) continue;
                    for (int dy = -1; dy <= 1; dy++)
                    {
                        int yy = y + dy; if (yy < 0 || yy >= ny) continue;
                        int row = (zz * ny + yy) * nx;
                        for (int dx = -1; dx <= 1; dx++)
                        {
                            int xx = x + dx; if (xx < 0 || xx >= nx) continue;
                            sum += f[row + xx];
                            count++;
                        }
                    }
                }
                g[(z * ny + y) * nx + x] = sum / count;
            }
            return g;
        }
    }
}
