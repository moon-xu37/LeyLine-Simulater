### 环境配置记录

#### 导出/导入安装依赖
(venv)
pip freeze -l > requirements.txt

pip install -l -r requirements.txt


#### PYTHONPATH配置项目跟路径
https://code.visualstudio.com/docs/python/environments#_use-of-the-pythonpath-variable

in .vscode/settings:
"terminal.integrated.env.windows": {
  "PYTHONPATH": "src"
}
in .env
PYTHONPATH=src