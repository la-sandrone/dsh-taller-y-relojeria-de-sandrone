# WSL 独立盘：TeX Live 文档（texdoc.vhdx）

文件名: 用户笔记/部署/WSL-texdoc独立盘-20261103.md
摘要: 为 TeX Live 文档单开一块 100GB vhdx。目的不是容量，是**隔离膨胀**——texlive-doc
      解压 4.6 GB / 45993 文件，直接写进根分区 ext4.vhdx 就再也缩不回去。
状态: 已上线并端到端验通（2026-11-03）：`texdoc -l ctex` 与 `pdftotext` 双路可用。

---

## 配置

| 项 | 值 |
|---|---|
| 宿主文件 | `<D盘>:\Virtual Machines\WSL Data\texdoc.vhdx` |
| 类型 | **expandable**，上限 **51200 MB（50 GB）**（2026-11-04 由 100 GB 缩小重建） |
| 分区表 | **MBR**（msdos），单分区占满 |
| 文件系统 | ext4，卷标 **`TeX Live Doc`** |
| **挂载点** | **`/usr/share/doc/texlive`**（真实路径） |
| 间接入口 | `/usr/share/texmf-dist/doc` → 上面那个的 **symlink**（Arch 的分包做法） |

内容：45,993 个文件 / 10,641 个 PDF / 4.6 GB。宿主 vhdx **6.71 GB**（原 9.5 GB）。

创建（`diskpart`，脚本放 `<D盘>:\` 根下）：
`create vdisk file="..." maximum=51200 type=expandable`

## 三个坑（都是踩过的）

**① diskpart 的 `/s` 读不了带空格的脚本路径。**
`<D盘>:\Virtual Machines\WSL Data\...` 会报「无法打开或读取脚本文件」；脚本必须放 `<D盘>:\` 根，
但脚本**内容里**的 vhdx 路径带空格没关系。

**② 挂载点不能选 `/usr/share/texmf-dist/doc`。**
那是**符号链接**，`rmdir` 掉之后 pacman 装 texlive-doc 会重建为 symlink，
挂载点当场消失。真正的目录是 `/usr/share/doc/texlive`。
附带教训：`find` **默认不跟随符号链接**，所以 `find /usr/share/texmf-dist/doc -name '*.pdf'`
返回 0 —— 曾据此误判「没装上」。

**③ pacman 拒绝「存在但不属于任何包」的目录**，且 `--overwrite` 救不了：

> man pacman: *will not allow overwriting a directory with a file or installing packages
> with conflicting files and **directories***

所以顺序必须是：**卸载 → 让目录消失 → 装 → 搬 → 挂**，搬不掉的代价只能压到最低。

## 搬运：tar 流，不要 cp

```bash
sudo tar -C /usr/share/doc/texlive -cf - . | sudo tar -C /mnt/texdoc-staging -xpf -
```

**45,993 个文件 / 4.6 GB，实测 5.4 秒。** `cp -a` 走同规模是几十分钟量级——
texlive 的经典特征就是小文件海，每个文件一次 open/stat/read/close，cp 会死。

删原件同样用 `find -delete`（0.58 秒），不用 `rm -rf`：
```bash
sudo find /usr/share/doc/texlive -mindepth 1 -delete
```

## 元数据调优：50 GB 装 4.6 GB 小文件

### 为什么第一版吃到了 9.5 GB

`mkfs.ext4` **按卷大小**分配 inode，不按文件数：

```
100 GB 卷，默认 bytes-per-inode = 16384
→ 6,553,600 个 inode × 256 B = 1.64 GB 纯 inode 表
实际用了 45,993 个（0.7%）
```

另外两个隐性开销：保留块默认 **5%**（100 GB 上白占 5 GB）、journal 随卷涨到 128 MB。

### 重建参数（2026-11-04）

```bash
mkfs.ext4 -N 150000 \
          -J size=32 \
          -m 1 \
          -E lazy_itable_init=0,lazy_journal_init=0 \
          -L "TeX Live Doc" /dev/sdi1
```

| 参数 | 作用 | 效果 |
|---|---|---|
| `-N 150000` | **按真实条目数指定 inode**（实际 52,207，3 倍余量） | 1.64 GB → **39 MB** |
| `-J size=32` | journal 压到 32 MB | 128 MB → 32 MB |
| `-m 1` | 保留块 5% → 1% | 可用空间 +2 GB |
| `-E lazy_*_init=0` | 建时写全 inode 表与日志 | 避免后续随机写 |

**容量给多少不要紧，inode 数要按文件数给** —— 这两件事在 ext4 里本来就分得开。

重建后：`Inode count 153,600`，实用 52,207（34%）；vhdx 9.5 GB → **6.71 GB**。

### 重建流程（可复用）

```bash
tar -C /usr/share/doc/texlive -cpf <备份>.tar .     # ① 备份（4.6G 用 3m08s）
umount /usr/share/doc/texlive                       # ② 卸载
wsl --unmount "<D盘>:/.../texdoc.vhdx"                  # ③ 卸块设备
rm texdoc.vhdx && diskpart 建新盘                    # ④ 换盘
parted -s /dev/sdX mklabel msdos && mkpart primary ext4 0% 100%
mkfs.ext4 <优化参数>                                 # ⑤ 格式化
mount -L "TeX Live Doc" /usr/share/doc/texlive       # ⑥ 挂回
tar -C /usr/share/doc/texlive -xpf <备份>.tar        # ⑦ 解包（1m18s）
```

---

## ⚠️ 一次险情：差点对 Deepseek Harness 盘执行 mklabel（2026-11-04）

**事故经过**：重建时用 `awk '$2=="50G" && $3==""'` 猜目标盘，
`sdh`（**Deepseek Harness**，也是 50G、FSTYPE 挂在 `sdh1` 行上）先被匹配到，
于是对 `/dev/sdh` 执行了 `parted -s mklabel msdos`。

**为什么没炸**：

1. `mkpart` 被「正在使用」挡下 —— 分区已挂载，内核拒绝改表
2. `mklabel msdos` 对一个**本来就是 msdos** 的表，等于重写相同内容（分区仍 256s–13107199s）

验证结果：`git status` 正常、`dumpe2fs` 显示 `clean`、22 个顶层条目俱在。

**这是运气，不是保护。** 两条巧合缺一不可：
- 如果那块盘本来是 GPT → mklabel 会真的换表
- 如果它没挂载 → mkpart 会真的建新分区，覆盖原布局

### 硬规则一：认卷标，不认设备名

**卷标是唯一「既稳定又可读」的标识符**：

| 标识 | 稳定 | 可读 | 后果 |
|---|---|---|---|
| `/dev/sdX` | ❌ 随插拔与挂载顺序漂 | ❌ 无意义 | 只能靠上下文推断 → **本次就这样猜错了** |
| `UUID` | ✅ | ❌ 一串十六进制 | 人不可读，模型也只能比对 |
| **`LABEL`** | ✅ 跟着文件系统走 | ✅ 自带语义 | **两头都占** |

「可读」在这里不是审美问题——它让**人和模型能用同一句话确认目标**，不需要推断。
这与「事件 vs 记账」是同一条：**把语义写进标识符，判据就不用建在猜测上。**

**卷标的有无本身就是信号**：

```
无 LABEL 的盘  → 没被用过，是操作对象
有 LABEL 的盘  → 有数据，别碰
```

新建 vhdx 分区后必然无卷标，`mkfs` 时才打上——流程天然带一道闸。
**这比「验大小」硬**：大小会巧合（`sdh` 与 `sdi` 都是 50G），**卷标不会巧合**。

### 硬规则二：操作前四步

```bash
TARGET=/dev/sdX                                          # ① 硬编码，不猜、不用 awk
lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT "$TARGET"     # ② 人眼看：**目标必须是空 LABEL**
[ "$(lsblk -n -o SIZE "$TARGET")" = "  50G" ] || exit 1  # ③ 验大小
[ -z "$(lsblk -n -o FSTYPE "$TARGET")" ] || exit 1       # ④ 验空
```

### 硬规则三：挂载一律走卷标

```bash
mount -L "TeX Live Doc" "$MNT"                           # 首选
mount "/dev/disk/by-label/TeX\x20Live\x20Doc" "$MNT"    # 备选（卷标含空格）
```

**永不用 `/dev/sdX` 挂载。** 本仓库的自动挂载脚本从第一天就是这么写的，
只是这条没被写成规则——所以重建磁盘时没人遵守，才有了那次险情。

### 为什么这三条值得写死

**`parted mklabel` 无提示、不可撤销，比 `rm` 危险得多** —— `rm` 还有 `-i`，它只有 `-s`。
凡是「一条命令能抹掉整块盘」的操作，前一步必须是**人眼看 lsblk 输出里那个 LABEL**，
不是脚本推断，也不是「大小对上了应该就是它」。

## 自动挂载

`/home/.wsl_vhdx_automount.sh` 末尾有独立一段（**在原来那个 `if ! mountpoint -q "$MOUNT_POINT"` 块之外**——
/home 已挂时原块整段跳过，放里面就永远补不上）：

```bash
TEXDOC_VHD="<D盘>:/Virtual Machines/WSL Data/texdoc.vhdx"
TEXDOC_LABEL="TeX Live Doc"
TEXDOC_MNT="/usr/share/doc/texlive"

if ! mountpoint -q "$TEXDOC_MNT"; then
    powershell.exe -Command "wsl --mount --vhd \"$TEXDOC_VHD\" --bare" > /dev/null 2>&1
    sleep 3
    mkdir -p "$TEXDOC_MNT"
    mount -L "$TEXDOC_LABEL" "$TEXDOC_MNT" 2>/dev/null \
        || mount "/dev/disk/by-label/TeX\x20Live\x20Doc" "$TEXDOC_MNT"
fi
```

备份：`.wsl_vhdx_automount.sh.bak-20261103-*`（两代，改挂载点前后各一份）。

## 验证

```bash
df -h /usr/share/doc/texlive                  # /dev/sdi1，4.6G 已用
find /usr/share/doc/texlive -name '*.pdf' | wc -l   # 10641
texdoc -l ctex                                # 非空
pdftotext -f 1 -l 1 /usr/share/doc/texlive/latex/ctex/ctex.pdf -   # 出中文
```

## 一个意外收获：WSLg 一直是通的

`texdoc ctex` 会**直接弹窗**（不是只能输出路径）——因为

```
DISPLAY=:0   WAYLAND_DISPLAY=wayland-0   /mnt/wslg 存在（含 PulseAudio）
PDF 默认关联 = mupdf.desktop
```

⇒ **「WSL 只有控制台端点」这个假设是错的。** 图形一直在，只是没人触发过。
以后查 TeX 文档可以直接看 PDF，不必先 `pdftotext`。

## 打扫卫生

`sudo fstrim -v /` → 修剪 977.4 GiB；`sudo fstrim -v /usr/share/doc/texlive` → 45.2 GiB。
但 **fstrim 只告诉底层哪些块空闲，不会缩小 ext4.vhdx 文件本身**；
真要缩宿主文件，还得再跑 `<D盘>:\Virtual Machines\WSL Data\压缩WSL磁盘.cmd`（或 Windows 侧
`Optimize-VHD` / `diskpart compact vdisk`）。

**其他四块盘（<user> / Other / Build Temp / Deepseek Harness）未做任何改动。**
