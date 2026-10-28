/**
 * Midscene 落盘报告磁盘守护 —— 防 midscene_run 目录无限增长吃穿宿主机磁盘。
 *
 * 会话正常 dispose 时已删自己那份报告（automation.ts），但两条泄漏路径没盖：
 *  - 进程崩溃/被 kill 时活跃会话没走 dispose → 报告残留；
 *  - Midscene 除 report/ 外还写 log/ output/ 等 dump 产物。
 * 单份报告可达 19MB，真机长期跑会积几百 MB（实测 332MB）。
 *
 * 两道：①启动全清（进程重启＝所有旧报告都是孤儿，内存态会话表也没了）；
 * ②周期清超龄（>maxAge 的文件——正常会话报告 dispose 即删，活跃会话报告
 * mtime 是最近的且单用例受 300s RPC 上限约束，超龄只会命中孤儿）。
 */

import fs from 'node:fs';
import path from 'node:path';

import { log } from './log.js';

const DEFAULT_SWEEP_INTERVAL_MS = 30 * 60_000; // 30 分钟周期兜底
const DEFAULT_MAX_AGE_MS = 60 * 60_000; // 清 1 小时前的（远超单用例上限）

/** 递归删 dir 下 mtime ≤ cutoff 的**文件**（保留目录结构）。best-effort，
 *  单文件失败（并发删/权限）跳过不中断。返回删除文件数。 */
async function purgeDir(dir: string, cutoff: number): Promise<number> {
  let entries: fs.Dirent[];
  try {
    entries = await fs.promises.readdir(dir, { withFileTypes: true });
  } catch {
    return 0; // 目录不存在
  }
  let deleted = 0;
  for (const e of entries) {
    const fp = path.join(dir, e.name);
    if (e.isDirectory()) {
      deleted += await purgeDir(fp, cutoff);
    } else if (e.isFile()) {
      try {
        const st = await fs.promises.stat(fp);
        if (st.mtimeMs <= cutoff) {
          await fs.promises.unlink(fp);
          deleted++;
        }
      } catch {
        /* 并发删/权限：跳过 */
      }
    }
  }
  return deleted;
}

/**
 * 清 baseDir/midscene_run 下 mtime 早于 now-maxAgeMs 的文件。
 * maxAgeMs=0 → 删全部（启动清孤儿）。返回删除文件数。
 */
export async function purgeMidsceneFiles(baseDir: string, maxAgeMs: number): Promise<number> {
  const root = path.join(baseDir, 'midscene_run');
  return purgeDir(root, Date.now() - maxAgeMs);
}

/** 报告磁盘守护：启动全清 + 周期清超龄。 */
export class ReportCleaner {
  private timer: NodeJS.Timeout | undefined;

  constructor(
    private readonly baseDir: string,
    private readonly opts: { sweepIntervalMs?: number; maxAgeMs?: number } = {},
  ) {}

  /** 启动：立即全清孤儿（maxAge=0）+ 起周期兜底定时器。 */
  async start(): Promise<void> {
    try {
      const n = await purgeMidsceneFiles(this.baseDir, 0);
      if (n) log('info', '启动清理 Midscene 落盘报告（孤儿）', { deleted: n });
    } catch (err) {
      log('warn', '启动清理 Midscene 报告失败', { error: String(err) });
    }
    const interval = this.opts.sweepIntervalMs ?? DEFAULT_SWEEP_INTERVAL_MS;
    const maxAge = this.opts.maxAgeMs ?? DEFAULT_MAX_AGE_MS;
    this.timer = setInterval(() => {
      void purgeMidsceneFiles(this.baseDir, maxAge)
        .then((d) => {
          if (d) log('info', '周期清理超龄 Midscene 报告', { deleted: d });
        })
        .catch(() => {});
    }, interval);
    // 清理不应拖住进程退出
    this.timer.unref?.();
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = undefined;
  }
}
