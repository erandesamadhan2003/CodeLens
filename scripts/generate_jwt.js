import jwt from 'jsonwebtoken';
import { v4 as uuidv4 } from 'uuid';

const JWT_SECRET = process.env.JWT_SECRET || 'secret';
const userId = process.argv[2] || uuidv4();
const token = jwt.sign({ id: userId, username: 'testuser' }, JWT_SECRET, { expiresIn: '1h' });
console.log(token);
