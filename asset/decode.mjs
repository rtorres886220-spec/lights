// Decode the meshopt/quantized GLB into a plain GLB Blender can import.
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { dequantize } from '@gltf-transform/functions';
import { MeshoptDecoder } from 'meshoptimizer';
const [,, inp, out] = process.argv;
await MeshoptDecoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.decoder': MeshoptDecoder });
const doc = await io.read(inp);
for (const e of doc.getRoot().listExtensionsUsed()) if (['EXT_meshopt_compression','KHR_mesh_quantization'].includes(e.extensionName)) e.dispose();
await doc.transform(dequantize());
await io.write(out, doc);
console.log('decoded', out);
