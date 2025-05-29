const express = require('express');
const session = require('express-session');
const multer = require('multer');
const path = require('path');
const fs = require('fs-extra');
const { v4: uuidv4 } = require('uuid');
const { exec } = require('child_process');
const OpenAI = require('openai');
const bodyParser = require('body-parser');
require('dotenv').config();

// Initialize Express app
const app = express();
const port = process.env.PORT || 5000;

// Configure OpenAI
const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY || "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"
});
const OPENAI_MODEL = process.env.OPENAI_MODEL || "gpt-4o";

// Configure middleware
app.use(bodyParser.urlencoded({ extended: true }));
app.use(bodyParser.json());
app.use(express.static('public'));
app.use('/static', express.static('static'));
app.use('/generated', express.static('generated'));

// Configure session
app.use(session({
  secret: process.env.SESSION_SECRET || 'change_me',
  resave: false,
  saveUninitialized: true
}));

// Configure multer for file uploads
const storage = multer.diskStorage({
  destination: function (req, file, cb) {
    const uploadDir = path.join(__dirname, 'static', 'uploads');
    fs.ensureDirSync(uploadDir);
    cb(null, uploadDir);
  },
  filename: function (req, file, cb) {
    const uniqueId = uuidv4().replace(/-/g, '');
    const extension = path.extname(file.originalname);
    cb(null, uniqueId + extension);
  }
});

const upload = multer({ 
  storage: storage,
  fileFilter: function (req, file, cb) {
    // Accept images only
    if (!file.originalname.match(/\.(jpg|jpeg|png|gif)$/i)) {
      return cb(new Error('Only image files are allowed!'), false);
    }
    cb(null, true);
  }
});

// Set view engine
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Load CV templates
const CV_TEMPLATES = require('./config.json');

// Helper functions
function getTemplateMeta(templateId) {
  return CV_TEMPLATES.find(t => t.id === templateId) || null;
}

function loadSchema(templateMeta) {
  const schemaPath = path.join(__dirname, path.dirname(templateMeta.latex_path), 'schema.json');
  return JSON.parse(fs.readFileSync(schemaPath, 'utf8'));
}

function parseFormData(schema, formData, files) {
  const data = {};
  
  for (const section of schema.sections) {
    for (const field of section.fields) {
      const fieldId = field.id;
      const fieldType = field.type || 'text';
      
      if (fieldType === 'file') {
        if (files && files[fieldId]) {
          data[fieldId] = files[fieldId].filename;
        } else {
          data[fieldId] = '';
        }
      } else if (fieldType === 'array') {
        // Handle array fields (like experience, education)
        data[fieldId] = [];
        
        // Find all keys that match the pattern fieldId[index][subfield]
        const arrayPattern = new RegExp(`^${fieldId}\\[(\\d+)\\]\\[(.+)\\]$`);
        const arrayEntries = {};
        
        for (const key in formData) {
          const match = key.match(arrayPattern);
          if (match) {
            const [, index, subfield] = match;
            if (!arrayEntries[index]) {
              arrayEntries[index] = {};
            }
            arrayEntries[index][subfield] = formData[key];
          }
        }
        
        // Convert object to array
        for (const index in arrayEntries) {
          data[fieldId].push(arrayEntries[index]);
        }
      } else {
        data[fieldId] = formData[fieldId] || '';
      }
    }
  }
  
  return data;
}

async function renderLatex(templateMeta, context) {
  const templatePath = path.join(__dirname, templateMeta.latex_path);
  const templateDir = path.dirname(templatePath);
  const templateContent = fs.readFileSync(templatePath, 'utf8');
  
  // Simple template rendering (for complex cases, we'd use a proper template engine)
  let renderedContent = templateContent;
  
  for (const key in context) {
    const value = context[key];
    
    // Handle different types of values
    if (typeof value === 'string') {
      // Escape special LaTeX characters
      const escapedValue = value
        .replace(/\\/g, '\\textbackslash{}')
        .replace(/&/g, '\\&')
        .replace(/%/g, '\\%')
        .replace(/\$/g, '\\$')
        .replace(/#/g, '\\#')
        .replace(/_/g, '\\_')
        .replace(/\{/g, '\\{')
        .replace(/\}/g, '\\}')
        .replace(/~/g, '\\textasciitilde{}')
        .replace(/\^/g, '\\textasciicircum{}');
      
      // Replace {{ key }} with the value
      const regex = new RegExp(`\\{\\{\\s*${key}\\s*\\}\\}`, 'g');
      renderedContent = renderedContent.replace(regex, escapedValue);
    } else if (Array.isArray(value)) {
      // For arrays, we need to handle them specially based on the template
      // This is a simplified approach - for complex templates, use a proper template engine
      
      // Example: Handle jobs array
      if (key === 'jobs') {
        let jobsContent = '';
        for (const job of value) {
          jobsContent += `\\textsc{${job.title}} at \\textit{${job.company}}`;
          if (job.location) {
            jobsContent += ` (${job.location})`;
          }
          jobsContent += ` \\dates{${job.start_date}--${job.end_date}} \\\\\n`;
          
          if (job.bullets) {
            const bulletPoints = job.bullets.split('\n').filter(line => line.trim());
            for (const bullet of bulletPoints) {
              jobsContent += `\\smaller{${bullet}}\\is\n`;
            }
          }
        }
        
        // Replace the jobs loop in the template
        const jobsRegex = /\{% for job in jobs %\}([\s\S]*?)\{% endfor %\}/;
        renderedContent = renderedContent.replace(jobsRegex, jobsContent);
      }
      
      // Example: Handle degrees array
      if (key === 'degrees') {
        let degreesContent = '';
        for (const degree of value) {
          degreesContent += `\\textsc{${degree.degree}}. \\textit{${degree.institution}}. \\dates{${degree.dates}} \\\\\n`;
        }
        
        // Replace the degrees loop in the template
        const degreesRegex = /\{% for deg in degrees %\}([\s\S]*?)\{% endfor %\}/;
        renderedContent = renderedContent.replace(degreesRegex, degreesContent);
      }
      
      // Example: Handle certifications array
      if (key === 'certifications') {
        let certsContent = '';
        for (const cert of value) {
          certsContent += `\\smaller{\\textsc{${cert.title}}}, \\textit{${cert.issuer}}. \\dates{${cert.date}} \\\\\n`;
        }
        
        // Replace the certifications loop in the template
        const certsRegex = /\{% for cert in certifications %\}([\s\S]*?)\{% endfor %\}/;
        renderedContent = renderedContent.replace(certsRegex, certsContent);
      }
      
      // Handle skills list
      if (key === 'skills') {
        let skillsContent = '';
        for (const skill of value) {
          skillsContent += `  \\item ${skill}\n`;
        }
        
        // Replace the skills loop in the template
        const skillsRegex = /\{% for skill in skills\.splitlines\(\) if skill\.strip\(\) %\}([\s\S]*?)\{% endfor %\}/;
        renderedContent = renderedContent.replace(skillsRegex, skillsContent);
      }
    }
  }
  
  // Clean up any remaining template tags
  renderedContent = renderedContent
    .replace(/\{%\s*raw\s*%\}([\s\S]*?)\{%\s*endraw\s*%\}/g, '$1')
    .replace(/\{%\s*if\s*[\s\S]*?%\}([\s\S]*?)\{%\s*endif\s*%\}/g, '$1')
    .replace(/\{%\s*for\s*[\s\S]*?%\}([\s\S]*?)\{%\s*endfor\s*%\}/g, '')
    .replace(/\{\{\s*[\s\S]*?\s*\}\}/g, '');
  
  return renderedContent;
}

async function cleanLatexWithGPT(texContent) {
  try {
    const completion = await openai.chat.completions.create({
      model: OPENAI_MODEL,
      messages: [
        {
          role: "system",
          content: "You are a LaTeX expert. The document must be compilable with pdflatex only. Fix any errors, restore commands incompatible with fontspec or xelatex, improve layout (long lines, cut items) but DO NOT MODIFY the content. Return only the final code without comment."
        },
        {
          role: "user",
          content: texContent
        }
      ]
    });
    
    const cleanedContent = completion.choices[0].message.content.trim();
    return cleanedContent.replace(/^```latex\n|```$/g, '');
  } catch (error) {
    console.error('Error cleaning LaTeX with GPT:', error);
    return texContent; // Return original if GPT fails
  }
}

async function compilePDF(texContent, templateMeta, context) {
  // Create a unique build directory
  const buildId = uuidv4().replace(/-/g, '');
  const buildDir = path.join(__dirname, 'generated', buildId);
  const templateDir = path.join(__dirname, path.dirname(templateMeta.latex_path));
  
  // Copy template directory to build directory
  await fs.ensureDir(buildDir);
  await fs.copy(templateDir, buildDir);
  
  // Write the rendered LaTeX content to main.tex
  const texPath = path.join(buildDir, 'main.tex');
  await fs.writeFile(texPath, texContent, 'utf8');
  
  // Copy photo if it exists
  if (context.photo) {
    const photoSrc = path.join(__dirname, 'static', 'uploads', context.photo);
    if (await fs.pathExists(photoSrc)) {
      await fs.copy(photoSrc, path.join(buildDir, context.photo));
    }
  }
  
  // Run pdflatex
  return new Promise((resolve, reject) => {
    exec(`cd ${buildDir} && pdflatex -interaction=nonstopmode main.tex`, (error, stdout, stderr) => {
      if (error) {
        console.error(`pdflatex error: ${error}`);
        console.error(`stdout: ${stdout}`);
        console.error(`stderr: ${stderr}`);
        
        // Try to read the log file for better error reporting
        try {
          const logContent = fs.readFileSync(path.join(buildDir, 'main.log'), 'utf8');
          reject(new Error(`LaTeX compilation failed: ${logContent.slice(0, 1500)}`));
        } catch (logError) {
          reject(new Error(`LaTeX compilation failed: ${error.message}`));
        }
        return;
      }
      
      const pdfPath = path.join(buildDir, 'main.pdf');
      resolve(pdfPath);
    });
  });
}

async function editLatexWithGPT(texContent, instruction) {
  try {
    const completion = await openai.chat.completions.create({
      model: OPENAI_MODEL,
      messages: [
        {
          role: "system",
          content: "You are a LaTeX expert. Apply the instruction and return only the final code."
        },
        {
          role: "user",
          content: `Instruction: ${instruction}\n---\n${texContent}`
        }
      ]
    });
    
    const editedContent = completion.choices[0].message.content.trim();
    return editedContent.replace(/^```latex\n|```$/g, '');
  } catch (error) {
    console.error('Error editing LaTeX with GPT:', error);
    throw new Error(`GPT editing failed: ${error.message}`);
  }
}

// Routes
app.get('/', (req, res) => {
  res.render('index', { templates: CV_TEMPLATES });
});

app.get('/select/:templateId', (req, res) => {
  const templateId = req.params.templateId;
  const templateMeta = getTemplateMeta(templateId);
  
  if (!templateMeta) {
    return res.redirect('/');
  }
  
  req.session.templateId = templateId;
  req.session.formSchema = null;
  req.session.cvData = null;
  
  res.redirect('/form');
});

app.get('/form', (req, res) => {
  if (!req.session.templateId) {
    return res.redirect('/');
  }
  
  const templateMeta = getTemplateMeta(req.session.templateId);
  
  // Load schema if not already in session
  if (!req.session.formSchema) {
    req.session.formSchema = loadSchema(templateMeta);
  }
  
  res.render('form_schema', { 
    schema: req.session.formSchema,
    data: req.session.cvData || {}
  });
});

app.post('/form', upload.fields([
  { name: 'photo', maxCount: 1 }
]), async (req, res) => {
  if (!req.session.templateId) {
    return res.redirect('/');
  }
  
  const templateMeta = getTemplateMeta(req.session.templateId);
  const schema = req.session.formSchema || loadSchema(templateMeta);
  
  // Parse form data
  const formData = req.body;
  const files = req.files;
  
  // Convert file uploads to filenames
  let processedFiles = {};
  if (files) {
    for (const fieldName in files) {
      if (files[fieldName] && files[fieldName].length > 0) {
        processedFiles[fieldName] = files[fieldName][0].filename;
      }
    }
  }
  
  // Merge form data with file data
  const cvData = parseFormData(schema, formData, processedFiles);
  req.session.cvData = cvData;
  
  res.redirect('/preview');
});

app.get('/import', (req, res) => {
  if (!req.session.templateId) {
    return res.redirect('/');
  }
  
  res.render('import');
});

app.post('/import', upload.single('cv_file'), async (req, res) => {
  if (!req.session.templateId) {
    return res.redirect('/');
  }
  
  if (!req.file) {
    return res.redirect('/import');
  }
  
  // In a real implementation, we would extract data from the CV file
  // For now, we'll just redirect to the form
  res.redirect('/form');
});

app.get('/preview', async (req, res) => {
  if (!req.session.templateId || !req.session.cvData) {
    return res.redirect('/form');
  }
  
  try {
    const templateMeta = getTemplateMeta(req.session.templateId);
    
    // Render LaTeX
    const rawTex = await renderLatex(templateMeta, req.session.cvData);
    const cleanedTex = await cleanLatexWithGPT(rawTex);
    
    req.session.lastTex = cleanedTex;
    
    // Compile PDF
    const pdfPath = await compilePDF(cleanedTex, templateMeta, req.session.cvData);
    const relativePath = path.relative(path.join(__dirname, 'generated'), pdfPath);
    
    req.session.pdfFilename = relativePath;
    
    res.render('preview', { pdf_filename: relativePath });
  } catch (error) {
    console.error('Error generating preview:', error);
    res.status(500).send(`Error generating preview: ${error.message}`);
  }
});

app.get('/file/:filename', (req, res) => {
  const filePath = path.join(__dirname, 'generated', req.params.filename);
  res.sendFile(filePath);
});

app.get('/download', (req, res) => {
  if (!req.session.pdfFilename) {
    return res.redirect('/form');
  }
  
  const filePath = path.join(__dirname, 'generated', req.session.pdfFilename);
  res.download(filePath, 'cv.pdf');
});

app.post('/edit', async (req, res) => {
  if (!req.session.lastTex) {
    return res.redirect('/preview');
  }
  
  const instruction = req.body.instruction.trim();
  if (!instruction) {
    return res.redirect('/preview');
  }
  
  try {
    const newTex = await editLatexWithGPT(req.session.lastTex, instruction);
    const templateMeta = getTemplateMeta(req.session.templateId);
    const pdfPath = await compilePDF(newTex, templateMeta, req.session.cvData);
    
    req.session.lastTex = newTex;
    const relativePath = path.relative(path.join(__dirname, 'generated'), pdfPath);
    req.session.pdfFilename = relativePath;
    
    res.redirect('/preview');
  } catch (error) {
    console.error('Error editing CV:', error);
    res.status(500).send(`Error editing CV: ${error.message}`);
  }
});

// Start the server
app.listen(port, () => {
  console.log(`CV Generator app listening at http://localhost:${port}`);
});