const express = require('express');
const app = express();

app.get('/', (req, res) => {
    res.send('Hello, Node.js with VS Code!');
});

const port = 3000;
app.listen(port, () => {
    console.log(`Server running on http://localhost:${port}`);
});
