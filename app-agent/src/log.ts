/** 极简结构化日志：stdout/stderr 单行文本，pm2/systemd 直接收集，不引日志库 */

export type LogLevel = 'info' | 'warn' | 'error';

export function log(level: LogLevel, msg: string, extra?: Record<string, unknown>): void {
  const line =
    `${new Date().toISOString()} [${level.toUpperCase()}] ${msg}` +
    (extra ? ` ${JSON.stringify(extra)}` : '');
  if (level === 'error') console.error(line);
  else if (level === 'warn') console.warn(line);
  else console.log(line);
}
