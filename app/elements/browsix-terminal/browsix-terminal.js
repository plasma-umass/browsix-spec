var __extends = (this && this.__extends) || function (d, b) {
    for (var p in b) if (b.hasOwnProperty(p)) d[p] = b[p];
    function __() { this.constructor = d; }
    d.prototype = b === null ? Object.create(b) : (__.prototype = b.prototype, new __());
};
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var Terminal;
(function (Terminal_1) {
    'use strict';
    var ERROR = 'FLAGRANT SYSTEM ERROR';
    var Terminal = (function (_super) {
        __extends(Terminal, _super);
        function Terminal() {
            var _this = this;
            _super.call(this);
            this.ps1 = '$ ';
            this.extraNewline = false;
            window.Boot('XmlHttpRequest', ['index.json', 'fs', true], function (err, k) {
                if (err) {
                    console.log(err);
                    _this.$.term.innerHTML = ERROR;
                    throw new Error(err);
                }
                _this.kernel = k;
            }, { readOnly: false });
        }
        Terminal.prototype.attached = function () {
            this.$.term.addEventListener('input', this.onInput.bind(this));
        };
        Terminal.prototype.onInput = function (ev) {
            var _this = this;
            var txt = this.$.term.value;
            if (txt[txt.length - 1] !== '\n')
                return;
            var parts = txt.split('\n');
            var cmd = parts[parts.length - 2].substring(this.ps1.length).trim();
            if (cmd === '') {
                this.nextPrompt();
                return;
            }
            this.editable = false;
            var bg = cmd[cmd.length - 1] === '&';
            if (bg) {
                cmd = cmd.slice(0, -1).trim();
                setTimeout(function () { _this.editable = true; }, 0);
            }
            var completed = function (pid, code) {
                _this.editable = true;
            };
            var onInput = function (pid, out) {
                var newlinePos = _this.$.term.value.lastIndexOf('\n');
                var lastLine = _this.$.term.value.substr(newlinePos + 1);
                if (lastLine[0] === '$') {
                    if (!_this.extraNewline && out && out[out.length - 1] !== '\n') {
                        out += '\n';
                        _this.extraNewline = true;
                    }
                    else if (_this.extraNewline && out && out[out.length - 1] === '\n') {
                        out = out.slice(0, -1);
                        _this.extraNewline = false;
                    }
                    _this.$.term.value = _this.$.term.value.substr(0, newlinePos + 1) + out + lastLine;
                }
                else {
                    _this.extraNewline = false;
                    _this.$.term.value += out;
                }
            };
            this.kernel.system(cmd, completed, onInput, onInput);
        };
        Terminal.prototype.kernelChanged = function (_, oldKernel) {
            if (oldKernel) {
                console.log('unexpected kernel change');
                return;
            }
            this.editable = true;
        };
        Terminal.prototype.editableChanged = function (editable) {
            if (!editable)
                return;
            this.nextPrompt();
        };
        Terminal.prototype.nextPrompt = function () {
            this.$.term.value += this.ps1;
            var len = this.$.term.value.length;
            this.$.term.setSelectionRange(len, len);
            this.$.term.focus();
        };
        __decorate([
            property({ type: Object })
        ], Terminal.prototype, "kernel", void 0);
        __decorate([
            property({ type: Boolean })
        ], Terminal.prototype, "editable", void 0);
        __decorate([
            property({ type: String })
        ], Terminal.prototype, "ps1", void 0);
        __decorate([
            observe('kernel')
        ], Terminal.prototype, "kernelChanged", null);
        __decorate([
            observe('editable')
        ], Terminal.prototype, "editableChanged", null);
        Terminal = __decorate([
            component('browsix-terminal')
        ], Terminal);
        return Terminal;
    }(polymer.Base));
    Terminal.register();
})(Terminal || (Terminal = {}));
