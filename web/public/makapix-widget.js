/**
 * Makapix Widget - Standalone JavaScript widget for embedding comments and reactions
 * 
 * Usage:
 * <div id="makapix-widget" data-post-id="YOUR_POST_ID"></div>
 * <script src="https://makapix.club/makapix-widget.js"></script>
 */

(function() {
  'use strict';

  // Configuration
  const API_BASE_URL = window.MAKAPIX_API_URL || 'https://makapix.club/api';
  
  // Helper: Create element with classes and attributes
  function createElement(tag, options = {}) {
    const el = document.createElement(tag);
    if (options.className) el.className = options.className;
    if (options.text) el.textContent = options.text;
    if (options.html) el.innerHTML = options.html;
    if (options.attributes) {
      Object.entries(options.attributes).forEach(([key, value]) => {
        el.setAttribute(key, value);
      });
    }
    return el;
  }

  // Helper: Make API request
  async function apiRequest(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const token = localStorage.getItem('makapix_token');
    
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers
    };
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    
    const response = await fetch(url, {
      ...options,
      headers
    });
    
    if (!response.ok && response.status !== 401) {
      throw new Error(`API request failed: ${response.statusText}`);
    }
    
    return response;
  }

  // Helper: Format date
  function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    
    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    return date.toLocaleDateString();
  }

  // Widget class
  class MakapixWidget {
    constructor(container) {
      this.container = container;
      this.postId = container.getAttribute('data-post-id');
      
      if (!this.postId) {
        console.error('Makapix Widget: data-post-id attribute is required');
        return;
      }
      
      this.comments = [];
      this.reactions = { totals: {}, mine: [] };
      this.isAuthenticated = false;
      
      this.init();
    }
    
    async init() {
      this.container.innerHTML = '';
      this.container.className = 'makapix-widget';
      
      // Check authentication status
      await this.checkAuth();
      
      // Create widget structure
      this.createReactionsSection();
      this.createCommentsSection();
      
      // Load data
      await this.loadReactions();
      await this.loadComments();
      
      // Inject styles
      this.injectStyles();
    }
    
    async checkAuth() {
      const token = localStorage.getItem('makapix_token');
      if (!token) {
        this.isAuthenticated = false;
        return;
      }
      
      try {
        const response = await apiRequest('/auth/me');
        this.isAuthenticated = response.ok;
      } catch {
        this.isAuthenticated = false;
      }
    }
    
    createReactionsSection() {
      const section = createElement('div', { className: 'makapix-reactions-section' });
      
      const title = createElement('h3', { text: 'Reactions' });
      section.appendChild(title);
      
      const reactionsContainer = createElement('div', { 
        className: 'makapix-reactions-container'
      });
      reactionsContainer.id = `reactions-${this.postId}`;
      section.appendChild(reactionsContainer);
      
      const picker = createElement('div', { className: 'makapix-reaction-picker' });
      picker.innerHTML = `
        <button class="makapix-reaction-btn" data-emoji="❤️">❤️</button>
        <button class="makapix-reaction-btn" data-emoji="👍">👍</button>
        <button class="makapix-reaction-btn" data-emoji="🔥">🔥</button>
        <button class="makapix-reaction-btn" data-emoji="😍">😍</button>
        <button class="makapix-reaction-btn" data-emoji="🎨">🎨</button>
        <button class="makapix-reaction-btn" data-emoji="⭐">⭐</button>
      `;
      
      picker.querySelectorAll('.makapix-reaction-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.preventDefault();
          this.toggleReaction(btn.getAttribute('data-emoji'));
        });
      });
      
      section.appendChild(picker);
      this.container.appendChild(section);
    }
    
    createCommentsSection() {
      const section = createElement('div', { className: 'makapix-comments-section' });
      
      const title = createElement('h3', { text: 'Comments' });
      section.appendChild(title);
      
      // Comment form
      const form = createElement('form', { className: 'makapix-comment-form' });
      form.innerHTML = `
        <textarea 
          class="makapix-comment-input" 
          placeholder="Add a comment... ${this.isAuthenticated ? '' : '(posting as guest)'}"
          maxlength="2000"
        ></textarea>
        <button type="submit" class="makapix-comment-submit">Post Comment</button>
      `;
      
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        this.postComment();
      });
      
      section.appendChild(form);
      
      // Comments list
      const commentsList = createElement('div', { className: 'makapix-comments-list' });
      commentsList.id = `comments-${this.postId}`;
      section.appendChild(commentsList);
      
      this.container.appendChild(section);
    }
    
    async loadReactions() {
      try {
        const response = await apiRequest(`/posts/${this.postId}/reactions`);
        if (response.ok) {
          this.reactions = await response.json();
          this.renderReactions();
        }
      } catch (error) {
        console.error('Failed to load reactions:', error);
      }
    }
    
    renderReactions() {
      const container = document.getElementById(`reactions-${this.postId}`);
      if (!container) return;
      
      container.innerHTML = '';
      
      const totals = this.reactions.totals || {};
      const mine = this.reactions.mine || [];
      
      if (Object.keys(totals).length === 0) {
        container.innerHTML = '<p class="makapix-no-reactions">No reactions yet. Be the first!</p>';
        return;
      }
      
      Object.entries(totals).forEach(([emoji, count]) => {
        const isMine = mine.includes(emoji);
        const badge = createElement('span', {
          className: `makapix-reaction-badge ${isMine ? 'makapix-reaction-mine' : ''}`,
          html: `${emoji} <span class="makapix-reaction-count">${count}</span>`
        });
        
        badge.addEventListener('click', () => {
          this.toggleReaction(emoji);
        });
        
        container.appendChild(badge);
      });
    }
    
    async toggleReaction(emoji) {
      const isMine = (this.reactions.mine || []).includes(emoji);
      
      try {
        if (isMine) {
          // Remove reaction
          await apiRequest(`/posts/${this.postId}/reactions/${encodeURIComponent(emoji)}`, {
            method: 'DELETE'
          });
        } else {
          // Add reaction (check limit)
          if ((this.reactions.mine || []).length >= 5) {
            alert('You can only add up to 5 reactions per post.');
            return;
          }
          
          await apiRequest(`/posts/${this.postId}/reactions/${encodeURIComponent(emoji)}`, {
            method: 'PUT'
          });
        }
        
        // Reload reactions
        await this.loadReactions();
      } catch (error) {
        console.error('Failed to toggle reaction:', error);
        alert('Failed to update reaction. Please try again.');
      }
    }
    
    async loadComments() {
      try {
        const response = await apiRequest(`/posts/${this.postId}/comments`);
        if (response.ok) {
          const data = await response.json();
          this.comments = data.items || [];
          this.renderComments();
        }
      } catch (error) {
        console.error('Failed to load comments:', error);
      }
    }
    
    renderComments() {
      const container = document.getElementById(`comments-${this.postId}`);
      if (!container) return;
      
      container.innerHTML = '';
      
      if (this.comments.length === 0) {
        container.innerHTML = '<p class="makapix-no-comments">No comments yet. Be the first to comment!</p>';
        return;
      }
      
      // Group comments by parent (for threading)
      const topLevel = this.comments.filter(c => !c.parent_id);
      
      topLevel.forEach(comment => {
        container.appendChild(this.renderComment(comment));
        
        // Render replies (depth 1)
        const replies = this.comments.filter(c => c.parent_id === comment.id);
        if (replies.length > 0) {
          const repliesContainer = createElement('div', { className: 'makapix-comment-replies' });
          replies.forEach(reply => {
            repliesContainer.appendChild(this.renderComment(reply));
          });
          container.appendChild(repliesContainer);
        }
      });
    }
    
    renderComment(comment) {
      const div = createElement('div', { className: 'makapix-comment' });
      
      const header = createElement('div', { className: 'makapix-comment-header' });
      
      const authorName = comment.author_display_name || 'Unknown';
      const isGuest = authorName.startsWith('Guest_');
      
      header.innerHTML = `
        <span class="makapix-comment-author ${isGuest ? 'makapix-guest' : ''}">${authorName}</span>
        <span class="makapix-comment-date">${formatDate(comment.created_at)}</span>
      `;
      
      div.appendChild(header);
      
      const body = createElement('div', { 
        className: 'makapix-comment-body',
        text: comment.body
      });
      div.appendChild(body);
      
      // Reply button (only for depth 0 comments)
      if (comment.depth === 0) {
        const replyBtn = createElement('button', {
          className: 'makapix-comment-reply-btn',
          text: 'Reply'
        });
        replyBtn.addEventListener('click', () => {
          this.showReplyForm(comment.id);
        });
        div.appendChild(replyBtn);
      }
      
      return div;
    }
    
    showReplyForm(parentId) {
      // Find the comment element
      const commentElements = document.querySelectorAll('.makapix-comment');
      let targetComment = null;
      
      for (const el of commentElements) {
        if (el.querySelector('.makapix-comment-reply-btn')) {
          const comment = this.comments.find(c => c.id === parentId);
          if (comment) {
            targetComment = el;
            break;
          }
        }
      }
      
      if (!targetComment) return;
      
      // Remove any existing reply forms
      document.querySelectorAll('.makapix-reply-form').forEach(f => f.remove());
      
      // Create reply form
      const form = createElement('form', { className: 'makapix-reply-form' });
      form.innerHTML = `
        <textarea 
          class="makapix-comment-input" 
          placeholder="Write a reply..."
          maxlength="2000"
        ></textarea>
        <div class="makapix-reply-actions">
          <button type="submit" class="makapix-comment-submit">Post Reply</button>
          <button type="button" class="makapix-reply-cancel">Cancel</button>
        </div>
      `;
      
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        await this.postComment(parentId);
        form.remove();
      });
      
      form.querySelector('.makapix-reply-cancel').addEventListener('click', () => {
        form.remove();
      });
      
      targetComment.appendChild(form);
      form.querySelector('textarea').focus();
    }
    
    async postComment(parentId = null) {
      const form = parentId 
        ? document.querySelector('.makapix-reply-form')
        : document.querySelector('.makapix-comment-form');
      
      if (!form) return;
      
      const textarea = form.querySelector('textarea');
      const body = textarea.value.trim();
      
      if (!body) {
        alert('Please enter a comment.');
        return;
      }
      
      if (body.length > 2000) {
        alert('Comment is too long (max 2000 characters).');
        return;
      }
      
      try {
        const payload = { body };
        if (parentId) payload.parent_id = parentId;
        
        const response = await apiRequest(`/posts/${this.postId}/comments`, {
          method: 'POST',
          body: JSON.stringify(payload)
        });
        
        if (response.ok) {
          textarea.value = '';
          await this.loadComments();
        } else {
          const error = await response.json();
          alert(error.detail || 'Failed to post comment. Please try again.');
        }
      } catch (error) {
        console.error('Failed to post comment:', error);
        alert('Failed to post comment. Please try again.');
      }
    }
    
    injectStyles() {
      if (document.getElementById('makapix-widget-styles')) return;
      
      const style = createElement('style', { 
        attributes: { id: 'makapix-widget-styles' }
      });
      
      style.textContent = `
        .makapix-widget {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          max-width: 800px;
          margin: 20px auto;
          padding: 20px;
          background: #fff;
          border-radius: 8px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        .makapix-reactions-section,
        .makapix-comments-section {
          margin-bottom: 30px;
        }
        
        .makapix-widget h3 {
          font-size: 18px;
          font-weight: 600;
          margin: 0 0 15px 0;
          color: #333;
        }
        
        .makapix-reactions-container {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-bottom: 15px;
        }
        
        .makapix-reaction-badge {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          padding: 6px 12px;
          background: #f0f0f0;
          border-radius: 16px;
          font-size: 14px;
          cursor: pointer;
          transition: background 0.2s;
        }
        
        .makapix-reaction-badge:hover {
          background: #e0e0e0;
        }
        
        .makapix-reaction-badge.makapix-reaction-mine {
          background: #e3f2fd;
          border: 2px solid #2196f3;
        }
        
        .makapix-reaction-count {
          font-weight: 600;
          color: #666;
        }
        
        .makapix-reaction-picker {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
        }
        
        .makapix-reaction-btn {
          padding: 8px 12px;
          font-size: 20px;
          background: #fff;
          border: 2px solid #e0e0e0;
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.2s;
        }
        
        .makapix-reaction-btn:hover {
          border-color: #2196f3;
          transform: scale(1.1);
        }
        
        .makapix-comment-form,
        .makapix-reply-form {
          margin-bottom: 20px;
        }
        
        .makapix-comment-input {
          width: 100%;
          padding: 12px;
          border: 2px solid #e0e0e0;
          border-radius: 8px;
          font-family: inherit;
          font-size: 14px;
          resize: vertical;
          min-height: 80px;
          box-sizing: border-box;
        }
        
        .makapix-comment-input:focus {
          outline: none;
          border-color: #2196f3;
        }
        
        .makapix-comment-submit,
        .makapix-reply-cancel {
          margin-top: 8px;
          padding: 10px 20px;
          background: #2196f3;
          color: #fff;
          border: none;
          border-radius: 6px;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          transition: background 0.2s;
        }
        
        .makapix-comment-submit:hover {
          background: #1976d2;
        }
        
        .makapix-reply-cancel {
          background: #757575;
          margin-left: 8px;
        }
        
        .makapix-reply-cancel:hover {
          background: #616161;
        }
        
        .makapix-reply-actions {
          display: flex;
          gap: 8px;
        }
        
        .makapix-comment {
          padding: 15px;
          border: 1px solid #e0e0e0;
          border-radius: 8px;
          margin-bottom: 12px;
          background: #fafafa;
        }
        
        .makapix-comment-header {
          display: flex;
          align-items: center;
          gap: 12px;
          margin-bottom: 8px;
        }
        
        .makapix-comment-author {
          font-weight: 600;
          color: #333;
        }
        
        .makapix-comment-author.makapix-guest {
          color: #757575;
          font-style: italic;
        }
        
        .makapix-comment-date {
          font-size: 12px;
          color: #999;
        }
        
        .makapix-comment-body {
          color: #333;
          line-height: 1.5;
          margin-bottom: 8px;
          white-space: pre-wrap;
          word-wrap: break-word;
        }
        
        .makapix-comment-reply-btn {
          padding: 4px 12px;
          background: transparent;
          color: #2196f3;
          border: none;
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
        }
        
        .makapix-comment-reply-btn:hover {
          text-decoration: underline;
        }
        
        .makapix-comment-replies {
          margin-left: 40px;
        }
        
        .makapix-no-reactions,
        .makapix-no-comments {
          color: #999;
          font-style: italic;
          text-align: center;
          padding: 20px;
        }
      `;
      
      document.head.appendChild(style);
    }
  }

  // Auto-initialize widgets on page load
  function initWidgets() {
    const containers = document.querySelectorAll('[id^="makapix-widget"]');
    containers.forEach(container => {
      new MakapixWidget(container);
    });
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initWidgets);
  } else {
    initWidgets();
  }

  // Export for manual initialization
  window.MakapixWidget = MakapixWidget;
})();

