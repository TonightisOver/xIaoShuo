/**
 * Line-by-line diff engine using Longest Common Subsequence (LCS).
 */
export function computeLineDiff(oldStr, newStr) {
  const oldLines = oldStr ? oldStr.split('\n') : []
  const newLines = newStr ? newStr.split('\n') : []

  const n = oldLines.length
  const m = newLines.length

  // Performance Guard: Limit max lines to prevent memory exhaustion
  if (n > 2000 || m > 2000) {
    return [
      { type: 'removed', text: '... (文本行数超过 2000 行，已省略差异对比) ...' },
      { type: 'added', text: '... (请直接在上方切换至“显示纯文本”模式阅读新版本) ...' }
    ]
  }

  const dp = Array.from({ length: n + 1 }, () => Array(m + 1).fill(0))

  // DP computation
  for (let i = 1; i <= n; i++) {
    for (let j = 1; j <= m; j++) {
      if (oldLines[i - 1] === newLines[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1])
      }
    }
  }

  // Backtracking
  const result = []
  let i = n
  let j = m

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && oldLines[i - 1] === newLines[j - 1]) {
      result.unshift({ type: 'unchanged', text: oldLines[i - 1] })
      i--
      j--
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.unshift({ type: 'added', text: newLines[j - 1] })
      j--
    } else {
      result.unshift({ type: 'removed', text: oldLines[i - 1] })
      i--
    }
  }

  return result
}
