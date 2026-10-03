import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm'
import { CONFIG } from './config.js'

export const supabase = createClient(
  CONFIG.SUPABASE_URL,
  CONFIG.SUPABASE_ANON_KEY
)

let validAccessTokenPromise = null

export async function getValidAccessToken() {
  if (validAccessTokenPromise) return validAccessTokenPromise
  validAccessTokenPromise = (async () => {
    const { data: sessionData, error: sessionError } = await supabase.auth.getSession()
    if (sessionError) throw sessionError

    let session = sessionData?.session
    if (!session) return null

    const expiresSoon = session.expires_at && session.expires_at * 1000 < Date.now() + 60_000
    if (expiresSoon) {
      const { data: refreshData, error: refreshError } = await supabase.auth.refreshSession()
      if (refreshError) {
        refreshError.refreshFailed = true
        throw refreshError
      }
      session = refreshData?.session
    }
    return session?.access_token || null
  })()
  try {
    return await validAccessTokenPromise
  } finally {
    validAccessTokenPromise = null
  }
}

window.supabase = supabase
window.getValidAccessToken = getValidAccessToken

