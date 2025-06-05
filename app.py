import streamlit as st
from groq import Groq
import os
import tempfile
import PyPDF2
import docx
import re

# --- API Key Configuration ---
GROQ_API_KEY = st.secrets.get("GROQ_API_API_KEY")

if not GROQ_API_KEY:
    st.error("Groq API key not found. Please configure it in Streamlit secrets.")
    st.info("For Streamlit Cloud: Go to 'Secrets' in your app settings and add `GROQ_API_API_KEY = \"your_key_here\"`.")
    st.info("For local development: Create `.streamlit/secrets.toml` and add `GROQ_API_API_KEY = \"your_key_here\"` (and add `.streamlit/secrets.toml` to `.gitignore`).")
    st.stop()
else:
    client = Groq(api_key=GROQ_API_KEY)


# Initialize session state variables
if 'cv_analysis' not in st.session_state:
    st.session_state.cv_analysis = None
if 'career_suggestions' not in st.session_state:
    st.session_state.career_suggestions = None
if 'enhance_mode' not in st.session_state:
    st.session_state.enhance_mode = False
if 'test_taken' not in st.session_state:
    st.session_state.test_taken = False
if 'selected_skill' not in st.session_state:
    st.session_state.selected_skill = ""
if 'skills' not in st.session_state: # This holds skills from manual input for enhancement if no CV
    st.session_state.skills = ""
if 'user_answers' not in st.session_state:
    st.session_state.user_answers = []
if 'correct_answers' not in st.session_state:
    st.session_state.correct_answers = []
if 'test_questions_data' not in st.session_state: # To store parsed questions and options
    st.session_state.test_questions_data = []
if 'show_manual_suggestions' not in st.session_state:
    st.session_state.show_manual_suggestions = False
if 'show_cv_suggestions' not in st.session_state:
    st.session_state.show_cv_suggestions = False
if 'show_enhance_program' not in st.session_state:
    st.session_state.show_enhance_program = False
if 'show_test' not in st.session_state: # Explicitly manage test visibility
    st.session_state.show_test = False
if 'test_results' not in st.session_state:
    st.session_state.test_results = None
if 'enhancement_strategy' not in st.session_state:
    st.session_state.enhancement_strategy = None
if 'experience_level' not in st.session_state: # Store experience from form for consistency
    st.session_state.experience_level = "Student"
if 'extracted_cv_skills' not in st.session_state: # Store skills extracted from CV specifically
    st.session_state.extracted_cv_skills = ""
if 'current_skills_for_enhancement_list' not in st.session_state: # List version of skills
    st.session_state.current_skills_for_enhancement_list = []


# Function to parse questions and options more robustly
def parse_test_questions(test_content):
    questions_data = []
    # Split by "Question X:" or "X." to get individual questions, handling multiple formats
    raw_questions = re.split(r'(?:Question\s*\d+\s*:|^\d+\.\s)', test_content, flags=re.MULTILINE)
    for raw_q in raw_questions:
        raw_q = raw_q.strip()
        if not raw_q:
            continue

        lines = raw_q.split('\n')
        if not lines:
            continue

        question_text = lines[0].strip()
        options = []
        for line in lines[1:]:
            line = line.strip()
            # Ensure options are correctly formatted with A), B), C), D)
            if re.match(r'^[A-D]\)', line):
                options.append(line)
        
        # Only add question if both text and options are found and exactly 4 options
        if question_text and options and len(options) == 4:
            questions_data.append({"question": question_text, "options": options})
    return questions_data

# Sidebar setup
with st.sidebar:
    st.header("Additional Features")
    
    # CV Upload and Analysis
    st.subheader("Upload Your CV")
    uploaded_file = st.file_uploader("Choose a file (PDF or DOCX)", type=["pdf", "docx"])
    
    if uploaded_file is not None:
        # Reset display flags and states relevant to other modes
        st.session_state.show_manual_suggestions = False
        st.session_state.show_cv_suggestions = True # Keep CV suggestions visible
        st.session_state.show_enhance_program = False # Hide enhancement until 'Enhance Skill' is clicked
        st.session_state.enhance_mode = False # Turn off enhance mode initially
        st.session_state.test_taken = False
        st.session_state.test_questions_data = []
        st.session_state.user_answers = []
        st.session_state.correct_answers = []
        st.session_state.show_test = False
        st.session_state.test_results = None
        st.session_state.enhancement_strategy = None
        st.session_state.extracted_cv_skills = "" # Clear previous extracted skills

        with st.spinner("Analyzing your CV..."):
            try:
                text = ""
                if uploaded_file.type == "application/pdf":
                    pdf_reader = PyPDF2.PdfReader(uploaded_file)
                    for page in pdf_reader.pages:
                        text += page.extract_text() or ""
                elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                    doc = docx.Document(uploaded_file)
                    text = "\n".join([para.text for para in doc.paragraphs])
                
                if not text.strip():
                    st.warning("No text could be extracted from the document.")
                else:
                    # Get career advice based on CV
                    response = client.chat.completions.create(
                        model="llama3-70b-8192",
                        messages=[{
                            "role": "user",
                            "content": f"Analyze this CV and suggest 3 detailed career paths:\n{text[:10000]}\n"
                                       "Format each with:\n"
                                       "- Title\n- Description\n"
                                       "- Required Certifications\n"
                                       "- Average Salary Range\n"
                                       "- Growth Outlook"
                        }],
                        temperature=0.7,
                        max_tokens=1024
                    )
                    st.session_state.cv_analysis = response.choices[0].message.content
                    st.success("CV analysis complete! You can now use the 'Enhance Skill' feature in the sidebar.")
                    
                    # Also, extract skills from CV analysis immediately for later use
                    skill_response = client.chat.completions.create(
                        model="llama3-70b-8192",
                        messages=[{
                            "role": "user",
                            "content": f"From the following career analysis, extract a list of 3-5 key technical skills mentioned as 'Required Certifications' or skills implied as necessary for career growth. List them separated by commas. If no specific technical skills are mentioned, infer some general technical skills from the career paths (e.g., 'Python Programming', 'Data Analysis', 'Cloud Computing'). Do not include introductory phrases, just the comma-separated skills."
                                       f"\n\n{st.session_state.cv_analysis}"
                        }],
                        temperature=0.3,
                        max_tokens=200
                    )
                    st.session_state.extracted_cv_skills = re.sub(r'^(Skills:|Suggested skills:|Key technical skills:|Technical skills to enhance:)\s*', '', skill_response.choices[0].message.content, flags=re.IGNORECASE).strip()

            except Exception as e:
                st.error(f"Error processing CV: {str(e)}")
    
    # Skill Enhancement Section
    st.subheader("Enhance Your Skills")
    enhance_skill_button = st.button("Enhance Skill")
    
    if enhance_skill_button:
        # Check if either CV analysis has happened OR manual skills are entered
        if st.session_state.cv_analysis or (st.session_state.get('skills') and st.session_state.skills.strip()):
            st.session_state.enhance_mode = True
            st.session_state.show_enhance_program = True # Show skill enhancement section
            st.session_state.show_manual_suggestions = False # Hide other suggestions
            st.session_state.show_cv_suggestions = False # Hide other suggestions
            st.session_state.test_taken = False # Reset test state for new enhancement session
            st.session_state.test_questions_data = [] # Clear previous test questions
            st.session_state.user_answers = []
            st.session_state.correct_answers = []
            st.session_state.show_test = False # Ensure test is not shown initially
            st.session_state.test_results = None
            st.session_state.enhancement_strategy = None
            
            # DETERMINE SKILLS FOR ENHANCEMENT *IMMEDIATELY* AFTER BUTTON CLICK
            if st.session_state.cv_analysis and st.session_state.extracted_cv_skills:
                st.session_state.current_skills_for_enhancement_list = [s.strip() for s in st.session_state.extracted_cv_skills.split(',') if s.strip()]
            elif st.session_state.get('skills') and st.session_state.skills.strip():
                st.session_state.current_skills_for_enhancement_list = [s.strip() for s in st.session_state.skills.split(',') if s.strip()]
            else:
                st.session_state.current_skills_for_enhancement_list = [] # Should not happen with the outer if condition

            if st.session_state.current_skills_for_enhancement_list:
                # Set a default selected skill if not already set or not in the new list
                if st.session_state.selected_skill not in st.session_state.current_skills_for_enhancement_list:
                    st.session_state.selected_skill = st.session_state.current_skills_for_enhancement_list[0]
            else:
                st.warning("No skills found to enhance. Please upload your CV or enter your skills in the main form.")
                st.session_state.show_enhance_program = False
                st.session_state.enhance_mode = False
            
            st.rerun() # Rerun to display the enhancement program with correct skills and selected skill
        else:
            st.warning("Please first get career suggestions (by entering skills/interests) or upload your CV to enable skill enhancement.")

# Main content area
st.title("AI Career Advisor")

with st.form("career_form"):
    skills_input = st.text_input("Your Skills (comma separated):", value=st.session_state.skills, key="skills_input")
    interests = st.text_input("Your Interests (comma separated):", key="interests_input")
    
    experience_options = ["Student", "Entry-level", "Mid-career", "Senior"]
    current_experience_index = experience_options.index(st.session_state.get('experience_level', 'Student'))
    experience = st.selectbox("Experience Level:",
                              experience_options,
                              index=current_experience_index,
                              key="experience_input")

    submitted = st.form_submit_button("Get Career Advice")

if submitted:
    if not all([skills_input.strip(), interests.strip()]):
        st.error("Please fill in your skills and interests.")
    else:
        # Reset display flags
        st.session_state.show_manual_suggestions = True
        st.session_state.show_cv_suggestions = False # IMPORTANT: Hide CV suggestions
        st.session_state.show_enhance_program = False
        st.session_state.enhance_mode = False # Turn off enhance mode
        st.session_state.test_taken = False
        st.session_state.cv_analysis = None # IMPORTANT: Clear CV analysis results
        st.session_state.extracted_cv_skills = "" # Clear extracted CV skills
        st.session_state.show_test = False
        st.session_state.test_results = None
        st.session_state.enhancement_strategy = None
        
        st.session_state.skills = skills_input # Store skills for potential enhancement
        st.session_state.experience_level = experience # Store experience for consistent enhancement advice

        with st.spinner("Generating career paths..."):
            try:
                response = client.chat.completions.create(
                    model="llama3-70b-8192",
                    messages=[{
                        "role": "user",
                        "content": f"Suggest 3 detailed career paths for:\n"
                                   f"Skills: {st.session_state.skills}\nInterests: {interests}\n" # Use session state skills
                                   f"Experience: {experience}\n"
                                   "Format each with:\n"
                                   "- Title\n- Description\n"
                                   "- Required Certifications\n"
                                   "- Average Salary Range\n"
                                   "- Growth Outlook"
                    }],
                    temperature=0.7,
                    max_tokens=1024
                )

                st.session_state.career_suggestions = response.choices[0].message.content
                st.success("Career suggestions generated! You can now use the 'Enhance Skill' feature.")
                
            except Exception as e:
                st.error(f"Error communicating with Groq API: {str(e)}")

# Display career suggestions based on manual input
if st.session_state.show_manual_suggestions and st.session_state.career_suggestions:
    st.markdown("---")
    st.subheader("Recommended Career Paths (Based on Manual Input)")
    st.write(st.session_state.career_suggestions)

# Display career suggestions based on CV analysis
if st.session_state.show_cv_suggestions and st.session_state.cv_analysis:
    st.markdown("---")
    st.subheader("Career Suggestions Based on Your CV")
    st.write(st.session_state.cv_analysis)

# Skill Enhancement Flow
if st.session_state.enhance_mode and st.session_state.show_enhance_program:
    st.markdown("---")
    st.subheader("Skill Enhancement Program")

    # Use the pre-determined skill list
    skill_list = st.session_state.current_skills_for_enhancement_list

    if not skill_list:
        st.warning("No skills found to enhance. Please ensure your CV was analyzed or you entered skills.")
        st.session_state.show_enhance_program = False
        st.session_state.enhance_mode = False
        # Remove the stop() here to allow the warning to be displayed without blocking
    else:
        st.write("Suggested skills to enhance:")
        st.write(", ".join(skill_list)) # Display as comma separated string

        # Maintain selected skill across reruns
        if st.session_state.selected_skill not in skill_list:
            st.session_state.selected_skill = skill_list[0] # Default to first skill if previous selection is gone

        selected_skill = st.selectbox("Select a skill to enhance:", skill_list, index=skill_list.index(st.session_state.selected_skill))
        st.session_state.selected_skill = selected_skill
        
        # Determine experience level for learning materials and test
        effective_experience_level = st.session_state.get('experience_level', 'Student') 

        if selected_skill:
            # Generate learning materials only once per skill selection or on initial load
            if 'learning_materials' not in st.session_state or st.session_state.get('last_selected_skill_for_materials') != selected_skill:
                with st.spinner(f"Preparing {selected_skill} learning materials..."):
                    materials_response = client.chat.completions.create(
                        model="llama3-70b-8192",
                        messages=[{
                            "role": "user",
                            "content": f"Create a beginner-friendly learning guide for {selected_skill} suitable for a {effective_experience_level} level individual. "
                                       "Include:\n"
                                       "1. Key concepts (bullet points)\n"
                                       "2. Recommended free online resources (actual URLs if possible, otherwise generic types like 'Coursera course', 'YouTube tutorial series')\n"
                                       "3. A practical 2-week study plan (1 hour daily, detailing topics for each day)\n"
                                       "4. Expected outcomes after completing this guide."
                        }],
                        temperature=0.5,
                        max_tokens=1024
                    )
                    st.session_state.learning_materials = materials_response.choices[0].message.content
                    st.session_state.last_selected_skill_for_materials = selected_skill # Store the last selected skill for materials
            
            st.markdown("### Learning Materials")
            st.write(st.session_state.learning_materials)
            
            # --- Test Section ---
            # Show "Take Test" button only if test hasn't been taken and not already showing a test
            if not st.session_state.test_taken and not st.session_state.show_test:
                if st.button("Take Test"):
                    with st.spinner("Generating test questions..."):
                        test_response = client.chat.completions.create(
                            model="llama3-70b-8192",
                            messages=[{
                                "role": "user",
                                "content": f"Create a 5-question multiple choice test about {selected_skill} at {effective_experience_level} level. "
                                           "Each question should have a question number (e.g., 'Question 1:'), the question text, and exactly 4 options (A), B), C), D)) on separate lines. "
                                           "Ensure there's a blank line between each question and its options. "
                                           "Provide the correct answers at the very end, each on a new line, prefixed with 'Correct Answer ' followed by the question number and the correct option (e.g., 'Correct Answer 1: A', 'Correct Answer 2: B'). "
                                           "Do NOT show correct answers within the questions or options."
                            }],
                            temperature=0.3,
                            max_tokens=1024
                        )
                        test_content = test_response.choices[0].message.content
                        
                        # Split questions from correct answers using regex for robustness
                        parts = re.split(r'(Correct Answer \d+: [A-D])', test_content)
                        raw_questions_part = ""
                        raw_correct_answers_part = ""

                        # Reconstruct parts more carefully
                        for i, part in enumerate(parts):
                            if re.match(r'Correct Answer \d+: [A-D]', part):
                                raw_correct_answers_part += part.strip() + "\n"
                            else:
                                raw_questions_part += part.strip() + "\n"

                        if not raw_questions_part.strip() or not raw_correct_answers_part.strip():
                             st.error("Could not parse test questions or correct answers properly. Please try again.")
                             st.session_state.test_taken = False
                             st.session_state.show_test = False
                             # st.stop() # Removed st.stop() to allow error message to be displayed without blocking
                             st.rerun() # Rerun to try generating again
                        
                        st.session_state.test_questions_data = parse_test_questions(raw_questions_part)
                        
                        # Parse correct answers robustly
                        st.session_state.correct_answers = []
                        for line in raw_correct_answers_part.split('\n'):
                            match = re.search(r'Correct Answer \d+: ([A-D])', line)
                            if match:
                                st.session_state.correct_answers.append(match.group(1))
                        
                        # Validate that we have 5 questions and 5 answers
                        if len(st.session_state.test_questions_data) != 5 or len(st.session_state.correct_answers) != 5:
                            st.warning(f"Generated {len(st.session_state.test_questions_data)} questions and {len(st.session_state.correct_answers)} answers. Expected 5. Please click 'Take Test' again.")
                            st.session_state.test_taken = False
                            st.session_state.show_test = False # Keep button visible
                            st.session_state.test_questions_data = [] # Clear so it tries again
                            st.session_state.correct_answers = []
                            # No rerun here, let user click again
                            
                        else:
                            # Ensure user_answers list is correctly sized and initialized to None
                            st.session_state.user_answers = [None] * len(st.session_state.test_questions_data)
                            st.session_state.show_test = True
                            st.rerun() # Rerun to display the test questions immediately
            
            # Display test if show_test flag is true and test hasn't been taken yet
            if st.session_state.show_test and not st.session_state.test_taken:
                st.markdown("### Skill Assessment Test")
                
                if st.session_state.test_questions_data:
                    with st.form("skill_test_form"):
                        # We need to capture current selections for submission
                        temp_user_answers = list(st.session_state.user_answers) # Copy to allow local modification

                        for i, q_data in enumerate(st.session_state.test_questions_data):
                            st.markdown(f"**Question {i+1}:** {q_data['question']}")
                            
                            # Use a unique key for each radio button
                            selected_option_index = None
                            if temp_user_answers[i] is not None:
                                try:
                                    selected_option_index = q_data['options'].index(temp_user_answers[i])
                                except ValueError: # In case the options change on rerun (unlikely but safe)
                                    selected_option_index = None

                            temp_user_answers[i] = st.radio(
                                f"Select answer for Question {i+1}:",
                                q_data['options'],
                                key=f"q_{i}_radio",
                                index=selected_option_index # Pre-select if previously answered
                            )
                        
                        submit_test_button = st.form_submit_button("Submit Test")

                        if submit_test_button:
                            st.session_state.user_answers = temp_user_answers # Update session state with final selections

                            if None in st.session_state.user_answers:
                                st.warning("Please answer all questions before submitting.")
                            else:
                                # Calculate score
                                score = 0
                                for i in range(len(st.session_state.test_questions_data)):
                                    if i < len(st.session_state.user_answers) and i < len(st.session_state.correct_answers):
                                        user_selected_option_char = st.session_state.user_answers[i][0] if st.session_state.user_answers[i] else ""
                                        if user_selected_option_char == st.session_state.correct_answers[i]:
                                            score += 1
                                
                                total_questions = len(st.session_state.test_questions_data)
                                percentage = (score / total_questions) * 100 if total_questions > 0 else 0
                                
                                st.session_state.test_results = (
                                    f"### Test Results\n"
                                    f"- **Score:** {score}/{total_questions}\n"
                                    f"- **Percentage:** {percentage:.0f}%\n"
                                )
                                # Generate enhancement strategy based on results and selected skill
                                with st.spinner("Generating personalized enhancement strategy..."):
                                    enhancement_prompt = f"Based on a test score of {percentage:.0f}% in {selected_skill} for a {effective_experience_level} level, provide a detailed strategy for improvement. " \
                                                        "Include:\n" \
                                                        "1. Key areas to focus on (specific concepts based on the skill)\n" \
                                                        "2. Suggested learning activities (e.g., practice problems, projects, advanced readings)\n" \
                                                        "3. A recommended study time commitment per day/week (e.g., 'Dedicate 1-2 hours daily for the next 3 weeks')\n" \
                                                        "4. A few advanced resources or next steps for continued learning (e.g., specific books, online courses, certifications).\n" \
                                                        "5. A concluding message encouraging the user to continue enhancing their skill."

                                    strategy_response = client.chat.completions.create(
                                        model="llama3-70b-8192",
                                        messages=[{"role": "user", "content": enhancement_prompt}],
                                        temperature=0.6,
                                        max_tokens=1024
                                    )
                                    st.session_state.enhancement_strategy = strategy_response.choices[0].message.content

                                st.session_state.test_taken = True # Mark test as taken
                                st.session_state.show_test = False # Hide the test form
                                st.rerun() # Rerun to display results and strategy
                else:
                    st.warning("No test questions available. Please click 'Take Test' to generate them.")
                        
            if st.session_state.test_results and st.session_state.test_taken:
                st.markdown(st.session_state.test_results)
                st.write("After the test assessment, we have a plan to enhance your skill. If you want to continue improving, click on the 'Enhance Skill' button in the sidebar.")
                
                if st.session_state.enhancement_strategy:
                    st.markdown("### Personalized Enhancement Strategy")
                    st.write(st.session_state.enhancement_strategy)

                # Reset for new skill or re-take test
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Retake Test for This Skill"):
                        st.session_state.test_taken = False
                        st.session_state.show_test = False # Allow test button to reappear
                        st.session_state.test_results = None
                        st.session_state.enhancement_strategy = None
                        st.session_state.user_answers = [] # Clear previous answers
                        st.session_state.test_questions_data = [] # Clear test questions so it regenerates
                        st.rerun()
                with col2:
                    if st.button("Enhance Another Skill"):
                        st.session_state.test_taken = False
                        st.session_state.enhance_mode = True # Keep enhance mode on
                        st.session_state.show_enhance_program = True # Keep this section visible
                        st.session_state.test_results = None # Clear previous results
                        st.session_state.enhancement_strategy = None
                        st.session_state.test_questions_data = [] # Clear test questions
                        st.session_state.user_answers = [] # Clear user answers
                        st.session_state.correct_answers = [] # Clear correct answers
                        st.session_state.show_test = False # Hide the test form
                        st.rerun()
    # else: # Removed this else block, as the outer 'if not skill_list' handles this case
    #    st.warning("No skills found to enhance. Please upload your CV or enter your skills.")
