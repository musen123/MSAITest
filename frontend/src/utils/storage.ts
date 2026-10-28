const STORAGE_PREFIX = 'code_rag_'

export const storage = {
  get<T>(key: string, defaultValue?: T): T | null {
    const value = localStorage.getItem(STORAGE_PREFIX + key)
    if (value === null) return defaultValue ?? null
    try {
      return JSON.parse(value) as T
    } catch {
      return value as unknown as T
    }
  },

  set(key: string, value: unknown): void {
    const stringValue = typeof value === 'string' ? value : JSON.stringify(value)
    localStorage.setItem(STORAGE_PREFIX + key, stringValue)
  },

  remove(key: string): void {
    localStorage.removeItem(STORAGE_PREFIX + key)
  },

  clear(): void {
    const keys = Object.keys(localStorage)
    keys.forEach(key => {
      if (key.startsWith(STORAGE_PREFIX)) {
        localStorage.removeItem(key)
      }
    })
  },
}
