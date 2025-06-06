// src/supabaseclient.js
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = 'https://tnofvhrlhszfvdikctie.supabase.co';
const supabaseAnonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRub2Z2aHJsaHN6ZnZkaWtjdGllIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDY3NjYzOTgsImV4cCI6MjA2MjM0MjM5OH0.E0AcNezaBq3zXn861HmXQV300LToxzS6CqToJNamJgc';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
