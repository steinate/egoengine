# InternDataEngine 修改

上游：`https://github.com/InternRobotics/InternDataEngine.git`

共同基线：`2a0a21f2c836df97c925729084e13d68950b4deb`。

- `interndataengine-isaac41.patch`：VLA-Infra 实际部署源码与上游的差异，包括控制器修复和轨迹导出工具。排除生成的 output 配置；未修改远端运行文件。
- `interndataengine-local.patch`：本机 `human-pair-integration` 分支的差异，包括场景记录/导出、重放和几何测试。它不是远端部署的完整替代。

两份补丁各自应用于干净基线，**不要叠加应用**。分别通过 `git apply --check`。

```bash
git clone https://github.com/InternRobotics/InternDataEngine.git
cd InternDataEngine
git switch -c human-pair 2a0a21f2c836df97c925729084e13d68950b4deb
git apply --check /absolute/path/to/patches/interndataengine-isaac41.patch
git apply /absolute/path/to/patches/interndataengine-isaac41.patch
```

这只恢复引擎源码修改。完整任务仍需本仓库阶段代码、环境依赖和已有数据资产。
`work/engine-human-pair.patch` 是早期历史补丁，保留追溯，不作为当前部署入口。
补丁散列和本机分支提交见 `provenance/`。
