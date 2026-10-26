# contextbudget

**给上下文算账，看预算花在哪。**

`contextbudget` —— 按片段统计上下文的 token 占用，标出超预算的部分与可裁剪的低价值片段。

- 零依赖，Python 3.10+ 标准库即可运行
- 单文件，`contextbudget.py` 拷走就能用
- 不联网、不写文件

<!-- ipos:install -->
## 安装

零依赖，Python 3.10+ 即可：

```bash
pip install kons4go-contextbudget
```

装完直接用命令名调用：

```bash
contextbudget --help
```

也可以不用安装，直接把 `contextbudget.py` 拷走用——它只依赖标准库。

## 为什么需要它

上下文工具多只报总长度；contextbudget 按片段归因并指出超预算的来源，给出可裁剪候选而非笼统建议。

它遵守下面几条自己定的规矩：

1. **归因，不是建议**。超预算就说清楚是哪一段吃掉的，不笼统地说「建议精简」。
2. **估算就标明是估算**。token 数依赖具体分词器，这里给的是量级估计。
3. **不自动压缩**。压缩是另一件事，本工具只负责把账摊开。

## 用法

```bash
python contextbudget.py --file context.txt --budget 4000
python contextbudget.py --file context.txt --budget 4000 --json
```

加 `--json` 可以拿到机器可读的结果，便于接到流水线里。

## 已知局限

- 按章节切分预算，不理解段落之间的语义依赖。
- token 数按字符估算，与具体模型的 tokenizer 有偏差。
- 不生成摘要，只告诉你哪里超了。

## 跑测试

```bash
python test_contextbudget.py
```

测试用独立的断言与临时数据，不污染工作目录。

## 来源与参考

- Python 标准库文档：<https://docs.python.org/3/>
- GitHub 仓库：<https://github.com/kons4go/contextbudget>

---

## 关于作者

kons4go 做上下文预算分配相关的问题。这个工具先替你回答一个具体问题，再谈别的。

- 个人主页：<https://kons4go.github.io>
- 仓库：<https://github.com/kons4go/contextbudget>

## 许可

MIT，见 [LICENSE](LICENSE)。
