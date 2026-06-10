export interface StockSearchItem {
  symbol: string
  name: string
  aliases: string[]
}

export interface StockSearchResult extends StockSearchItem {
  label: string
  value: string
}

const STOCK_SEARCH_INDEX: StockSearchItem[] = [
  { symbol: '600519.SH', name: '贵州茅台', aliases: ['gzmoutai', 'gzmt', 'maotai', '茅台'] },
  { symbol: '600036.SH', name: '招商银行', aliases: ['zhaoshangyinhang', 'zsyh', 'cmb'] },
  { symbol: '601318.SH', name: '中国平安', aliases: ['zhongguopingan', 'zgpa', 'pingan'] },
  { symbol: '000001.SZ', name: '平安银行', aliases: ['pinganyinhang', 'payh'] },
  { symbol: '000333.SZ', name: '美的集团', aliases: ['meidejituan', 'mdjt', 'midea'] },
  { symbol: '000858.SZ', name: '五粮液', aliases: ['wuliangye', 'wly'] },
  { symbol: '002415.SZ', name: '海康威视', aliases: ['haikangweishi', 'hkws', 'hikvision'] },
  { symbol: '002594.SZ', name: '比亚迪', aliases: ['biyadi', 'byd'] },
  { symbol: '300750.SZ', name: '宁德时代', aliases: ['ningdeshidai', 'ndsd', 'catl'] },
  { symbol: '601166.SH', name: '兴业银行', aliases: ['xingyeyinhang', 'xyyh'] },
  { symbol: '601398.SH', name: '工商银行', aliases: ['gongshangyinhang', 'gsyh', 'icbc'] },
  { symbol: '601857.SH', name: '中国石油', aliases: ['zhongguoshiyou', 'zgsy', 'petrochina'] },
  { symbol: '600030.SH', name: '中信证券', aliases: ['zhongxinzhengquan', 'zxzq', 'citic'] },
  { symbol: '600276.SH', name: '恒瑞医药', aliases: ['hengruiyiyao', 'hryy'] },
  { symbol: '600309.SH', name: '万华化学', aliases: ['wanhuahuaxue', 'whhx'] },
  { symbol: '600887.SH', name: '伊利股份', aliases: ['yiligufen', 'ylgf'] },
  { symbol: '601088.SH', name: '中国神华', aliases: ['zhongguoshenhua', 'zgsh'] },
  { symbol: '601899.SH', name: '紫金矿业', aliases: ['zijinkuangye', 'zjky'] },
  { symbol: '603259.SH', name: '药明康德', aliases: ['yaomingkangde', 'ymkd', 'wuxi'] },
  { symbol: '688981.SH', name: '中芯国际', aliases: ['zhongxinguoji', 'zxgj', 'smic'] },
]

function compact(value: string): string {
  return value.trim().toLowerCase().replace(/[\s._-]/g, '')
}

export function normalizeStockSymbolInput(input: string): string {
  const rawInput = input.includes('·') ? input.split('·')[0] : input
  const raw = rawInput.trim().toUpperCase()
  if (!raw) return ''

  const compacted = raw.replace(/[\s._-]/g, '')
  const prefixMatch = compacted.match(/^(SH|SZ|BJ)(\d{1,6})$/)
  if (prefixMatch) {
    return `${prefixMatch[2].padStart(6, '0')}.${prefixMatch[1]}`
  }

  const suffixMatch = compacted.match(/^(\d{1,6})(SH|SZ|BJ)$/)
  if (suffixMatch) {
    return `${suffixMatch[1].padStart(6, '0')}.${suffixMatch[2]}`
  }

  const dottedMatch = raw.match(/^(\d{1,6})\.(SH|SZ|BJ)$/)
  if (dottedMatch) {
    return `${dottedMatch[1].padStart(6, '0')}.${dottedMatch[2]}`
  }

  if (/^\d{1,6}$/.test(raw)) {
    let code = raw
    if (code.length === 5 && /^(60|68|30)/.test(code)) {
      code = `${code.slice(0, 3)}0${code.slice(3)}`
    } else {
      code = code.padStart(6, '0')
    }
    const exchange = /^[569]/.test(code) ? 'SH' : /^[48]/.test(code) ? 'BJ' : 'SZ'
    return `${code}.${exchange}`
  }

  return raw
}

export function searchStocks(query: string, limit = 8): StockSearchResult[] {
  const normalizedQuery = normalizeStockSymbolInput(query)
  const key = compact(query)
  const symbolKey = compact(normalizedQuery)
  if (!key) return STOCK_SEARCH_INDEX.slice(0, limit).map(toResult)

  const scored = STOCK_SEARCH_INDEX.map((item) => {
    const fields = [item.symbol, item.name, ...item.aliases].map(compact)
    const exact = fields.some((field) => field === key || field === symbolKey)
    const starts = fields.some((field) => field.startsWith(key) || field.startsWith(symbolKey))
    const includes = fields.some((field) => field.includes(key) || field.includes(symbolKey))
    return { item, score: exact ? 3 : starts ? 2 : includes ? 1 : 0 }
  })
    .filter(({ score }) => score > 0)
    .sort((a, b) => b.score - a.score || a.item.symbol.localeCompare(b.item.symbol))

  const results = scored.slice(0, limit).map(({ item }) => toResult(item))
  if (normalizedQuery && /^[0-9]{6}\.(SH|SZ|BJ)$/.test(normalizedQuery) && !results.some((item) => item.symbol === normalizedQuery)) {
    results.unshift({
      symbol: normalizedQuery,
      name: 'Custom symbol',
      aliases: [],
      label: `${normalizedQuery} · Custom symbol`,
      value: normalizedQuery,
    })
  }
  return results.slice(0, limit)
}

export function resolveStockInput(input: string): string {
  const normalizedQuery = normalizeStockSymbolInput(input)
  const exact = searchStocks(input, 1)[0]
  if (exact && !/^[0-9]{6}\.(SH|SZ|BJ)$/.test(normalizedQuery)) {
    return exact.symbol
  }
  return normalizedQuery
}

function toResult(item: StockSearchItem): StockSearchResult {
  return {
    ...item,
    label: `${item.symbol} · ${item.name}`,
    value: `${item.symbol} · ${item.name}`,
  }
}
