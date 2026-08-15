import axios from 'axios';
import readline from 'readline';

const payload = {
    runId: "123e4567-e89b-12d3-a456-426614174000",
    repositoryId: "123e4567-e89b-12d3-a456-426614174000",
    repoUrl: "https://github.com/codelens/does-not-exist.git",
    commitSha: "main",
    branch: "main"
};

async function test() {
    try {
        const response = await axios.post('http://localhost:8004/internal/analyze', payload, {
            responseType: 'stream',
        });
        
        const rl = readline.createInterface({ input: response.data });
        
        rl.on('line', (line) => {
            console.log("RECEIVED LINE:", line);
        });
        
        rl.on('close', () => {
            console.log("STREAM CLOSED");
        });
    } catch (e) {
        console.error("AXIOS ERROR", e.message);
    }
}
test();
