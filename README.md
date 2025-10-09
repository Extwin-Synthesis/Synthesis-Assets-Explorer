# Synthesis Assets Explorer

Discover massive open-source OpenUSD Sim‑Ready assets.<br><br>
[English](https://github.com/Extwin-Synthesis/Synthesis-Assets-Explorer/blob/main/README.md)|[中文](https://github.com/Extwin-Synthesis/Synthesis-Assets-Explorer/blob/main/README_zh.md)
<br><br>
Synthesis Assets Explorer is an Omniverse Kit extension that lets you browse and load high‑quality OpenUSD Sim‑Ready assets, architectural models, 3D Gaussian Splatting, and fully interactive scenes from https://synthesis.extwin.com into Omniverse applications (Isaac Sim, USD Composer). You can access and load assets from https://synthesis.extwin.com just like using NVIDIA’s official asset libraries.

## About the open source assets on https://synthesis.extwin.com

1) Articulated Sim‑Ready assets with joints, physics parameters, semantic, and PBR materials (continuously growing)
- Fidelity: assets are reverse‑modeled as close as possible to real‑world objects at 1:1 scale to ensure quality.
- Joints: most Sim‑Ready objects include joints and follow a unified naming convention.
- Collider: all objects include collision shapes. SDF is used by default; depending on the case, convex decomposition or convex hulls are used. You can adjust or add simplified colliders as needed.
- Rigid/Deformable: all Mesh prims are authored with appropriate rigid and deformable body.
- Coordinates: for convenience, the origin is set to the asset’s bottom center. No transforms are authored on Mesh prims; transforms are authored on parent Xform prims. Joint locations align exactly with Body1’s pivot.
- Semantic: all Xform prims include Semantic Data.
- Articulate Drive: all joints include a default Velocity Drive using acceleration‑based control (trajectory‑first) with damping and stiffness. You can tune parameters as required.
- Materials: PBR materials and physics materials are assigned according to visual material types, with baseline friction, density, etc. Adjust in your use case as needed.
- Script Nodes: some assets include script nodes to simulate more accurate physical behavior (e.g., hinge damping varying with door angle).
- References: see papers from open‑source project we contributed [ArtVIP](x-humanoid-artvip.github.io） for detailed descriptions.

2) Real‑world architectural models and spaces with lighting, PBR materials, and semantic data (continuously growing)
- Sourced from real project BIM (Building Information Model) model.
- Includes complete building component hierarchies and detailed properties.
- Currently provides partial spaces; full buildings/spaces will be added (residential, hospital, commercial, airport, substation, metro, etc.).

3) 3D Gaussian Splatting scenes in USDZ format (continuously growing)
- Based on the 3DGrut project.
- Currently offers sample scenes.

4) Fully interactive scenes composed from Sim‑Ready assets, models, and 3D Gaussian Splatting (continuously growing)

5) All assets are available in OpenUSD format for download (MJCF conversion to be released)

6) All assets can be viewed and interacted with directly in a WebGL‑enabled browser

7) Built‑in scene editor for assembling scenes in a WebGL‑enabled browser (Business User Only)

8) License: CC BY‑NC 4.0

## Installation

### Supported versions
- Omniverse Kit 107.3+
- Isaac Sim 5.0+

## Usage

1) Browsing

2) Sim‑Ready
- Because no test Fixed Joint is included by default, when pressing Play add a Ground Plane or add a Fixed Joint to a body.
- If you see rendering issues with transparent objects, adjust the relevant parameter accordingly.

3) Model
- Likewise, add a Ground Plane or a Fixed Joint.

4) 3D Gaussian Splatting
- To sharpen 3D Gaussian Splatting, adjust the following parameters; note this may affect other objects (pending Omniverse optimization).

5) Scenes
- Scenes may contain many assets. Some users may experience jitter from collisions when pressing Play; please fine‑tune as needed. We strive to eliminate such cases in testing, but due to hardware variability some users may still encounter them.

## Custom asset requests

If you have specific asset requirements, please let us know:

1) Open‑sourced assets
- If you agree to open‑source the assets, we will produce them free of charge per your specifications and upload them to https://synthesis.extwin.com. Please provide detailed requirements and any existing 3D models (3DS, glTF, USD, STP, IFC, or professional formats such as Revit, 3ds Max, SketchUp, SolidWorks, MicroStation, Inventor, Navisworks, etc.), or real‑world measurements with detailed photos. We cannot guarantee a timeline but will complete them as soon as possible.

2) Private assets
- If you prefer private assets, use the contact in the For Business section on https://synthesis.extwin.com. We will estimate cost and timeline per your requirements, create a dedicated private repository for you on https://synthesis.extwin.com, and upload the assets there.
