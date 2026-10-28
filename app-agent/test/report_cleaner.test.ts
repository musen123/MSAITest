/** 报告磁盘守护单测：递归清超龄文件 / 启动全清 / 目录不存在容错 */

import assert from 'node:assert/strict';
import { afterEach, beforeEach, describe, it } from 'node:test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { purgeMidsceneFiles } from '../src/report_cleaner.js';

let base: string;

function touch(rel: string, ageMs: number): string {
  const fp = path.join(base, rel);
  fs.mkdirSync(path.dirname(fp), { recursive: true });
  fs.writeFileSync(fp, 'x');
  const t = (Date.now() - ageMs) / 1000;
  fs.utimesSync(fp, t, t); // 设 atime/mtime 为 age 前
  return fp;
}

beforeEach(() => {
  base = fs.mkdtempSync(path.join(os.tmpdir(), 'rc-'));
});
afterEach(() => {
  fs.rmSync(base, { recursive: true, force: true });
});

describe('purgeMidsceneFiles', () => {
  it('maxAge=0 全清 midscene_run 下所有文件（启动清孤儿）', async () => {
    const a = touch('midscene_run/report/app-s1.html', 0);
    const b = touch('midscene_run/report/app-s2.html', 5_000);
    const c = touch('midscene_run/log/x.log', 0);
    const deleted = await purgeMidsceneFiles(base, 0);
    assert.equal(deleted, 3);
    assert.ok(!fs.existsSync(a) && !fs.existsSync(b) && !fs.existsSync(c));
  });

  it('周期清只删超龄文件（新文件保留）', async () => {
    const stale = touch('midscene_run/report/old.html', 2 * 60 * 60_000); // 2h 前
    const fresh = touch('midscene_run/report/new.html', 60_000); // 1min 前
    const deleted = await purgeMidsceneFiles(base, 60 * 60_000); // 清 1h 前
    assert.equal(deleted, 1);
    assert.ok(!fs.existsSync(stale), '超龄孤儿应删');
    assert.ok(fs.existsSync(fresh), '新报告应留');
  });

  it('递归进子目录 + 保留目录结构', async () => {
    touch('midscene_run/report/nested/deep.png', 0);
    const deleted = await purgeMidsceneFiles(base, 0);
    assert.equal(deleted, 1);
    // 目录结构保留（只删文件）
    assert.ok(fs.existsSync(path.join(base, 'midscene_run/report/nested')));
  });

  it('midscene_run 不存在 → 0，不抛', async () => {
    assert.equal(await purgeMidsceneFiles(base, 0), 0);
  });
});
