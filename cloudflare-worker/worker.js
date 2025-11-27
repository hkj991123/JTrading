/**
 * JTrading 订阅服务 - Cloudflare Worker
 * 
 * 功能：接收用户订阅请求，将邮箱追加到私有 Gist
 * 
 * 环境变量（在 Cloudflare Dashboard 中配置）：
 * - GIST_ID: Gist 的 ID（URL 中的那串字符）
 * - GIST_FILENAME: Gist 中的文件名（如 subscribers.txt）
 * - GITHUB_TOKEN: 具有 Gist 写入权限的 Personal Access Token
 * - ALLOWED_ORIGIN: 允许的前端域名（如 https://pear56.github.io）
 */

export default {
  async fetch(request, env) {
    // CORS 预检请求
    if (request.method === 'OPTIONS') {
      return handleCORS(env);
    }

    // 只接受 POST 请求
    if (request.method !== 'POST') {
      return jsonResponse({ error: '只支持 POST 请求' }, 405, env);
    }

    try {
      // 解析请求体
      const contentType = request.headers.get('content-type') || '';
      let email = '';

      if (contentType.includes('application/json')) {
        const body = await request.json();
        email = body.email;
      } else if (contentType.includes('form')) {
        const formData = await request.formData();
        email = formData.get('email');
      } else {
        return jsonResponse({ error: '不支持的 Content-Type' }, 400, env);
      }

      // 验证邮箱格式
      if (!email || !isValidEmail(email)) {
        return jsonResponse({ error: '请提供有效的邮箱地址' }, 400, env);
      }

      // 读取当前 Gist 内容
      const gistData = await getGist(env);
      if (!gistData) {
        return jsonResponse({ error: '无法读取订阅列表' }, 500, env);
      }

      const currentContent = gistData.files[env.GIST_FILENAME]?.content || '';
      const subscribers = currentContent.split('\n').map(line => line.trim().toLowerCase()).filter(Boolean);

      // 检查是否已订阅
      if (subscribers.includes(email.toLowerCase())) {
        return jsonResponse({ 
          success: true, 
          message: '您已经订阅过了，无需重复订阅' 
        }, 200, env);
      }

      // 追加新邮箱
      const newContent = currentContent.trim() + '\n' + email;
      const updated = await updateGist(env, newContent);

      if (updated) {
        return jsonResponse({ 
          success: true, 
          message: '订阅成功！当 RSI 触发买卖信号时，您将收到邮件通知。' 
        }, 200, env);
      } else {
        return jsonResponse({ error: '订阅失败，请稍后重试' }, 500, env);
      }

    } catch (err) {
      console.error('Worker error:', err);
      return jsonResponse({ error: '服务器内部错误' }, 500, env);
    }
  }
};

/**
 * 验证邮箱格式
 */
function isValidEmail(email) {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return re.test(email);
}

/**
 * 获取 Gist 内容
 */
async function getGist(env) {
  const response = await fetch(`https://api.github.com/gists/${env.GIST_ID}`, {
    headers: {
      'Authorization': `token ${env.GITHUB_TOKEN}`,
      'Accept': 'application/vnd.github.v3+json',
      'User-Agent': 'JTrading-Subscribe-Worker'
    }
  });

  if (response.ok) {
    return await response.json();
  }
  console.error('Failed to get gist:', response.status);
  return null;
}

/**
 * 更新 Gist 内容
 */
async function updateGist(env, newContent) {
  const response = await fetch(`https://api.github.com/gists/${env.GIST_ID}`, {
    method: 'PATCH',
    headers: {
      'Authorization': `token ${env.GITHUB_TOKEN}`,
      'Accept': 'application/vnd.github.v3+json',
      'User-Agent': 'JTrading-Subscribe-Worker',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      files: {
        [env.GIST_FILENAME]: {
          content: newContent
        }
      }
    })
  });

  return response.ok;
}

/**
 * CORS 预检响应
 */
function handleCORS(env) {
  return new Response(null, {
    status: 204,
    headers: {
      'Access-Control-Allow-Origin': env.ALLOWED_ORIGIN || '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Access-Control-Max-Age': '86400'
    }
  });
}

/**
 * JSON 响应
 */
function jsonResponse(data, status, env) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': env.ALLOWED_ORIGIN || '*'
    }
  });
}
