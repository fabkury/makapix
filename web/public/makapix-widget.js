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
          // Filter out invalid comments (depth > 2 or missing required fields)
          this.comments = (data.items || []).filter(comment => {
            if (!comment || typeof comment.id === 'undefined') return false;
            if (typeof comment.depth !== 'number' || comment.depth > 2) return false;
            if (!comment.body) return false;
            return true;
          });
          this.renderComments();
        } else {
          console.error('Failed to load comments:', response.status, response.statusText);
          this.showCommentsError();
        }
      } catch (error) {
        console.error('Failed to load comments:', error);
        this.showCommentsError();
      }
    }
    
    showCommentsError() {
      const container = document.getElementById(`comments-${this.postId}`);
      if (container) {
        container.innerHTML = '<p class="makapix-no-comments">Unable to load comments. Please refresh the page.</p>';
      }
    }
    
    renderComments() {
      const container = document.getElementById(`comments-${this.postId}`);
      if (!container) return;
      
      container.innerHTML = '';
      
      if (!this.comments || this.comments.length === 0) {
        container.innerHTML = '<p class="makapix-no-comments">No comments yet. Be the first to comment!</p>';
        return;
      }
      
      // Group comments by parent (for threading)
      const topLevel = this.comments.filter(c => c && !c.parent_id);
      
      if (topLevel.length === 0) {
        container.innerHTML = '<p class="makapix-no-comments">No visible comments.</p>';
        return;
      }
      
      topLevel.forEach(comment => {
        const commentDiv = this.renderCommentWithReplies(comment);
        if (commentDiv) {
          container.appendChild(commentDiv);
        }
      });
    }
    
    renderCommentWithReplies(comment) {
      if (!comment || !comment.id) {
        console.warn('Invalid comment detected, skipping:', comment);
        return null;
      }
      
      const commentDiv = this.renderComment(comment);
      if (!commentDiv) return null;
      
      // Find all replies to this comment (any depth)
      const replies = this.comments.filter(c => c && c.parent_id === comment.id);
      if (replies.length > 0) {
        const repliesContainer = createElement('div', { className: 'makapix-comment-replies' });
        replies.forEach(reply => {
          const replyDiv = this.renderCommentWithReplies(reply);
          if (replyDiv) {
            repliesContainer.appendChild(replyDiv);
          }
        });
        if (repliesContainer.children.length > 0) {
          // Append replies container to the content wrapper so it's hidden when folded
          const contentWrapper = commentDiv.querySelector('.makapix-comment-content');
          if (contentWrapper) {
            contentWrapper.appendChild(repliesContainer);
          } else {
            commentDiv.appendChild(repliesContainer);
          }
        }
      }
      
      return commentDiv;
    }
    
    renderComment(comment) {
      if (!comment || !comment.id) {
        console.warn('Invalid comment detected:', comment);
        return null;
      }
      
      const div = createElement('div', { 
        className: 'makapix-comment',
        attributes: { 'data-comment-id': String(comment.id) }
      });
      
      const header = createElement('div', { className: 'makapix-comment-header' });
      
      const authorName = comment.author_display_name || 'Unknown';
      const isGuest = authorName.startsWith('Guest_');
      
      // Fold/unfold button
      const foldBtn = createElement('button', {
        className: 'makapix-comment-fold-btn',
        attributes: { 'aria-label': 'Fold comment' },
        html: '▼'
      });
      foldBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.toggleFold(comment.id);
      });
      
      header.appendChild(foldBtn);
      
      const authorSpan = createElement('span', {
        className: `makapix-comment-author ${isGuest ? 'makapix-guest' : ''}`,
        text: authorName
      });
      header.appendChild(authorSpan);
      
      const dateSpan = createElement('span', {
        className: 'makapix-comment-date',
        text: formatDate(comment.created_at)
      });
      header.appendChild(dateSpan);
      
      div.appendChild(header);
      
      // Content wrapper (body + actions) - can be hidden when folded
      const contentWrapper = createElement('div', { className: 'makapix-comment-content' });
      
      const body = createElement('div', { 
        className: 'makapix-comment-body',
        text: comment.body || '[deleted]'
      });
      contentWrapper.appendChild(body);
      
      // Reply button (only for depth < 2, allowing replies up to depth 1)
      const depth = typeof comment.depth === 'number' ? comment.depth : 0;
      const actionsContainer = createElement('div', { className: 'makapix-comment-actions' });
      
      if (depth < 2) {
        const replyBtn = createElement('button', {
          className: 'makapix-comment-reply-btn',
          text: 'Reply'
        });
        replyBtn.addEventListener('click', () => {
          this.showReplyForm(comment.id);
        });
        actionsContainer.appendChild(replyBtn);
      }
      
      // Delete button (show for all comments, API will handle permission check)
      if (!comment.deleted_by_owner) {
        const deleteBtn = createElement('button', {
          className: 'makapix-comment-delete-btn',
          text: 'Delete'
        });
        deleteBtn.addEventListener('click', () => {
          this.confirmDelete(comment.id);
        });
        actionsContainer.appendChild(deleteBtn);
      }
      
      if (actionsContainer.children.length > 0) {
        contentWrapper.appendChild(actionsContainer);
      }
      
      div.appendChild(contentWrapper);
      
      return div;
    }
    
    toggleFold(commentId) {
      const commentIdStr = String(commentId);
      const commentElement = document.querySelector(`.makapix-comment[data-comment-id="${commentIdStr}"]`);
      if (!commentElement) return;
      
      const foldBtn = commentElement.querySelector('.makapix-comment-fold-btn');
      const isFolded = commentElement.classList.contains('makapix-folded');
      
      if (isFolded) {
        // Unfold: show content and child comments
        commentElement.classList.remove('makapix-folded');
        if (foldBtn) {
          foldBtn.textContent = '▼';
          foldBtn.setAttribute('aria-label', 'Fold comment');
        }
      } else {
        // Fold: hide content and child comments
        commentElement.classList.add('makapix-folded');
        if (foldBtn) {
          foldBtn.textContent = '▶';
          foldBtn.setAttribute('aria-label', 'Unfold comment');
        }
      }
    }
    
    showReplyForm(parentId) {
      // Find the comment element by data-comment-id attribute
      // Convert parentId to string to ensure proper matching
      const commentId = String(parentId);
      const targetComment = document.querySelector(`.makapix-comment[data-comment-id="${commentId}"]`);
      
      if (!targetComment) {
        console.error('Comment element not found for parentId:', parentId);
        return;
      }
      
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
      
      // Store parentId for form submission
      form.dataset.parentId = parentId;
      
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        await this.postComment(parentId);
        form.remove();
      });
      
      form.querySelector('.makapix-reply-cancel').addEventListener('click', () => {
        form.remove();
      });
      
      // Append form to the content wrapper so it's hidden when folded
      const contentWrapper = targetComment.querySelector('.makapix-comment-content');
      if (contentWrapper) {
        contentWrapper.appendChild(form);
      } else {
        // Fallback: append to comment element if content wrapper doesn't exist
        targetComment.appendChild(form);
      }
      form.querySelector('textarea').focus();
    }
    
    confirmDelete(commentId) {
      if (!confirm('Are you sure you want to delete this comment? This action cannot be undone.')) {
        return;
      }
      this.deleteComment(commentId);
    }
    
    async deleteComment(commentId) {
      try {
        const response = await apiRequest(`/posts/comments/${commentId}`, {
          method: 'DELETE'
        });
        
        if (response.ok || response.status === 204) {
          // Reload comments to show updated state
          await this.loadComments();
        } else {
          const error = await response.json().catch(() => ({ detail: 'Failed to delete comment' }));
          alert(error.detail || 'You don\'t have permission to delete this comment.');
        }
      } catch (error) {
        console.error('Failed to delete comment:', error);
        alert('Failed to delete comment. Please try again.');
      }
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
          gap: 8px;
          margin-bottom: 8px;
        }
        
        .makapix-comment-fold-btn {
          padding: 2px 6px;
          background: transparent;
          border: none;
          color: #666;
          font-size: 12px;
          cursor: pointer;
          line-height: 1;
          min-width: 20px;
          text-align: center;
          transition: color 0.2s;
        }
        
        .makapix-comment-fold-btn:hover {
          color: #2196f3;
        }
        
        .makapix-comment-content {
          /* Content wrapper - hidden when comment is folded */
        }
        
        .makapix-comment.makapix-folded .makapix-comment-content {
          display: none;
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
        
        .makapix-comment-actions {
          display: flex;
          gap: 12px;
          margin-top: 8px;
        }
        
        .makapix-comment-delete-btn {
          padding: 4px 12px;
          background: transparent;
          color: #f44336;
          border: none;
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
        }
        
        .makapix-comment-delete-btn:hover {
          text-decoration: underline;
          color: #d32f2f;
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

