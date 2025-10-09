# Synthesis Assets Explorer

Discover massive open-source OpenUSD Sim‑Ready assets.<br><br>
[English](https://github.com/Extwin-Synthesis/Synthesis-Assets-Explorer/blob/main/README.md)|[中文](https://github.com/Extwin-Synthesis/Synthesis-Assets-Explorer/blob/main/README_zh.md)
<br><br>

Synthesis Assets Explorer 是一个用于在 Omniverse 平台（Isaac Sim，USD Composer）中加载 https://synthesis.extwin.com 里 OpenUSD 格式的高质量 Sim‑Ready、建筑模型、3D 高斯泼溅以及全交互场景的插件。安装后，您可以像访问 NVIDIA 官方资产库一样访问和加载 https://synthesis.extwin.com 中的资产。

## 关于 https://synthesis.extwin.com 中的开源资产

1) 带有关节、物理参数、标注和 PBR 材质的 Sim‑Ready 资产库（持续添加中）
- 精细度：所有资产都尽量按照实物 1:1 逆向重建，确保质量
- 关节：大部分 Sim‑Ready 对象都包含关节，并按照统一命名规则进行命名
- 碰撞体：所有对象都添加了碰撞体（默认使用 SDF，但按照实际情况，也有部分使用凸分解和凸包，您可以按照要求调整或添加简化碰撞体）
- 刚体和软体：所有 Mesh 对象都按照实际添加了刚体和软体
- 坐标：为了方便使用，资产的坐标原点设定为资产的底部中心点；所有 Mesh 上均不添加 Transform，Transform 全部添加在其父级 Xform 上；关节的位置与 Body1 的 Pivot 点严格一致
- 标记：所有 Xform 上均添加 Semantic Data
- 驱动：所有关节均默认添加了 Velocity Driver，使用加速度驱动（轨迹优先），并添加阻尼和刚度，具体参数您可以在使用时按照要求调整
- 材质：所有材质均按照材质不同添加了对应的物理材质并给了基本的摩擦、密度等参数，具体使用中按照要求调整
- 脚本节点：部分资产包含脚本节点，用于模拟更加准确的物理效果（比如：随着开门角度改变，关节阻尼发生变化）
- 参考：我们参与的开源项目[ArtVIP](x-humanoid-artvip.github.io)相关的论文中有详细的描述，请参阅

2) 带有灯光、PBR 材质、标注的真实建筑的建筑模型和建筑空间（持续添加中）
- 来源于真实项目的 BIM（Building Information Model）模型
- 包含完整的建筑对象层级关系及详细属性
- 目前只是提供了建筑空间的局部，后续会陆续提供完整建筑空间的模型（家庭、医院、商业、机场、变电站、地铁……）

3) USDZ 格式的 3D 高斯泼溅场景（持续增加中）
- 基于 3DGrut 项目
- 目前仅提供了一些示例场景

4) 利用 Sim‑Ready、模型、3D 高斯泼溅搭建的全交互的场景（持续添加中）

5) 所有资产均有 OpenUSD 格式并支持下载（MJCF 格式转换功能待发布）

6) 所有资产均可在浏览器（支持 WebGL）中直接查看和操作

7) 内建场景编辑器，支持在浏览器（支持 WebGL）中搭建场景（Business User Only）

8) 开源协议：CC BY‑NC 4.0

## 版本要求
- Omniverse Kit 107.3+
- Isaac Sim 5.0+
- 
## 如何安装

## 如何使用

1) 浏览&加载

2) Sim‑Ready
- 因为没有添加测试用的 Fixed Joint，所以在 Play 时需要添加一个 Ground Plane 或在 Body 对象上添加 Fixed Joint
- 如果遇到透明物体显示异常，需要调整这个参数

3) Model
- 同样需要添加 Ground Plane 或者 Fixed Joint

4) 3D 高斯泼溅
- 如果需要让 3D 高斯泼溅更加清晰，可以修改以下参数，但会影响到其它对象（待 Omniverse 优化）

5) 场景
- 场景中因为资产较多，部分用户在 Play 时可能会有一些因为碰撞引起的抖动，需要您进行微调。我们尽量在测试时消除这些情况，但因为不同的硬件环境，部分用户依然会出现类似的情况。

## 如果您有明确的资产需求，请告知我们

1) 开源资产制作
- 如果您接受将这些资产开源，我们将按照您的要求免费制作，并上传至 https://synthesis.extwin.com。需要您提供详细的需求和既有的 3D 模型（3DS、glTF、USD、STP、IFC 或 Revit、3Ds Max、Sketchup、Solidworks、Microstation、Inventor、Navisowrks 等专业软件格式）或者实物的尺寸和尽量详细的照片（我们不能保证时间，会尽快完成）

2) 私有资产制作
- 如果您想制作私有资产，请使用 https://synthesis.extwin.com 中 For Business 部分的联系方式联系我们。我们将按照您的要求评估价格和完成时间，并在 https://synthesis.extwin.com 中为您创建专属的私有仓库并上转这些资产。
