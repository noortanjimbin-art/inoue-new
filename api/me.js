import { currentUser, json } from './_lib.js';

export default async function handler(req, res) {
  const me = await currentUser(req, res);
  if (!me) return;
  json(res, 200, me);
}
