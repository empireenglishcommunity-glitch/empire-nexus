import { evaluateWriting } from '../../../lib/ai'

export async function POST(request) {
  try {
    const { text, level } = await request.json()

    if (!text || text.trim().length < 5) {
      return Response.json({ error: 'Text too short' }, { status: 400 })
    }

    const result = await evaluateWriting(text.trim(), level || 'L0')

    if (result.error) {
      return Response.json({ error: result.error }, { status: 500 })
    }

    return Response.json(result)
  } catch (err) {
    return Response.json({ error: 'Server error' }, { status: 500 })
  }
}
